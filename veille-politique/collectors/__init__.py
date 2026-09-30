"""Orchestration par site : REST WordPress -> RSS -> HTML (ordre ajustable),
un site en panne n'arrête jamais les autres."""
from __future__ import annotations

import logging
import time

from core.http import DEFAULT_UA, HostUnreachable, PoliteSession, RobotsDisallowed

from . import html, rss, wordpress
from .base import CollectError, SiteConfig, SiteReport

log = logging.getLogger("veille.collect")

METHODES = {"rest": wordpress.collect, "rss": rss.collect, "html": html.collect}
ORDRE_DEFAUT = ["rest", "rss", "html"]


def method_order(site: SiteConfig, default=ORDRE_DEFAUT) -> list[str]:
    order = list(default)
    if site.methode_preferee in order:
        order.remove(site.methode_preferee)
        order.insert(0, site.methode_preferee)
    return order


def _is_blocked(msg: str) -> bool:
    return any(k in msg for k in ("403", "401", "429", "robots.txt", "anti-robot", "Forbidden",
                                  "Tunnel connection failed", "ProxyError"))


def collect_site(site: SiteConfig, start, end, opts: dict, storage=None) -> tuple[list, SiteReport]:
    rep = SiteReport(cle=site.cle, nom=site.nom, url=site.url, langue=site.langue,
                     a_confirmer=site.a_confirmer, methode_preferee=site.methode_preferee)
    http = PoliteSession(user_agent=opts.get("user_agent") or DEFAULT_UA,
                         delay=tuple(opts.get("delai", (1.0, 2.0))),
                         timeout=opts.get("timeout", 20), retries=opts.get("retries", 3),
                         respect_robots=opts.get("respect_robots", True))
    t0 = time.monotonic()
    articles: list = []
    order = method_order(site, opts.get("ordre_methodes", ORDRE_DEFAUT))
    for m in ORDRE_DEFAUT:
        rep.statuts[m] = "non tenté"
    blocked_all = True
    for m in order:
        try:
            if m == "html":
                arts = METHODES[m](site, http, start, end, opts, storage=storage)
            else:
                arts = METHODES[m](site, http, start, end, opts)
        except (CollectError, RobotsDisallowed, HostUnreachable) as e:
            msg = str(e)
            rep.statuts[m] = f"échec : {msg[:200]}"
            rep.erreurs.append(f"{m} : {msg[:300]}")
            blocked_all = blocked_all and _is_blocked(msg)
            if isinstance(e, HostUnreachable) or "site injoignable" in msg:
                for other in order[order.index(m) + 1:]:
                    rep.statuts[other] = "non tenté (site injoignable)"
                break
            log.info("[%s] %s en échec : %s", site.cle, m.upper(), msg[:200])
            continue
        except Exception as e:  # garde-fou : bug ou page inattendue
            rep.statuts[m] = f"erreur : {type(e).__name__}: {str(e)[:150]}"
            rep.erreurs.append(f"{m} : {type(e).__name__}: {e}")
            blocked_all = False
            log.exception("[%s] erreur inattendue en %s", site.cle, m)
            continue
        rep.statuts[m] = f"OK ({len(arts)})"
        rep.methode_utilisee = m
        articles = arts
        break
    rep.bloque = not rep.methode_utilisee and blocked_all
    rep.trouves = len(articles)
    rep.duree = round(time.monotonic() - t0, 1)
    rep.requetes = http.requests_count
    return articles, rep


__all__ = ["SiteConfig", "SiteReport", "collect_site", "method_order", "METHODES"]
