"""Client HTTP poli : User-Agent explicite, robots.txt, délai entre requêtes,
timeouts, retries avec backoff exponentiel."""
from __future__ import annotations

import logging
import random
import threading
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("veille.http")

DEFAULT_UA = ("VeillePolitiqueMA/1.0 (veille presse, lecture publique; "
              "+https://github.com/bencabdessamad/0tomate)")


class RobotsDisallowed(Exception):
    pass


class HostUnreachable(Exception):
    """Hôte injoignable (DNS, proxy, connexion refusée) : inutile d'insister."""


class PoliteSession:
    """Une instance par site (chaque site est collecté dans son propre fil)."""

    def __init__(self, user_agent: str = DEFAULT_UA, delay: tuple[float, float] = (1.0, 2.0),
                 timeout: float = 20.0, retries: int = 3, backoff: float = 1.5,
                 respect_robots: bool = True):
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Language": "ar,fr;q=0.9,en;q=0.5",
        })
        retry = Retry(total=retries, connect=retries, read=retries, status=retries,
                      backoff_factor=backoff, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET", "HEAD"), respect_retry_after_header=True,
                      raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self._robots: dict[str, RobotFileParser | None] = {}
        self._unreachable: dict[str, str] = {}
        self._last = 0.0
        self._lock = threading.Lock()
        self.requests_count = 0

    # -- politesse -----------------------------------------------------------
    def _wait(self):
        with self._lock:
            elapsed = time.monotonic() - self._last
            pause = random.uniform(*self.delay)
            if self._last and elapsed < pause:
                time.sleep(pause - elapsed)
            self._last = time.monotonic()

    def _robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = RobotFileParser()
            try:
                self._wait()
                r = self.session.get(base + "/robots.txt", timeout=self.timeout)
                self.requests_count += 1
                if r.status_code in (401, 403):
                    rp.disallow_all = True       # convention robotparser
                elif r.status_code >= 400:
                    rp.allow_all = True
                else:
                    rp.parse(r.text.splitlines())
            except requests.ConnectionError as e:
                # ProxyError, DNS, connexion refusée… (retries déjà épuisés)
                self._unreachable[base] = str(e)
                rp.allow_all = True
            except requests.RequestException as e:
                log.debug("robots.txt illisible pour %s (%s) : on considère autorisé", base, e)
                rp.allow_all = True
            self._robots[base] = rp
        return self._robots[base]

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        rp = self._robots_for(url)
        return rp.can_fetch(self.user_agent, url) if rp else True

    # -- requêtes ------------------------------------------------------------
    def get(self, url: str, **kwargs) -> requests.Response:
        allowed = self.allowed(url)
        parts = urlsplit(url)
        down = self._unreachable.get(f"{parts.scheme}://{parts.netloc}")
        if down:
            raise HostUnreachable(f"site injoignable : {down[:400]}")
        if not allowed:
            raise RobotsDisallowed(f"robots.txt interdit {url}")
        self._wait()
        kwargs.setdefault("timeout", self.timeout)
        r = self.session.get(url, **kwargs)
        self.requests_count += 1
        log.debug("GET %s -> %s", url, r.status_code)
        r.raise_for_status()
        return r
