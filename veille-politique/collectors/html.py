"""Repli : scraping HTML léger des rubriques politiques.
Lit la page de rubrique, suit les liens d'articles (même domaine) et
extrait titre / date / premier paragraphe avec les sélecteurs CSS de
sites.yaml, puis des heuristiques génériques (OpenGraph, JSON-LD…)."""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from core.dates import parse_any
from core.extract import clean_text, first_paragraph
from core.models import Article
from core.normalize import detect_language

from .base import CollectError

log = logging.getLogger("veille.html")

_GENERIC_LINKS = ["article h1 a", "article h2 a", "article h3 a", "h2.entry-title a",
                  "h3.entry-title a", ".post-title a", "article a", "h2 a", "h3 a"]
_SKIP_PATH = re.compile(r"/(category|categorie|tag|author|auteur|page|search|feed|wp-content|"
                        r"wp-json|contact|about|privacy)(/|$)|\.(jpg|jpeg|png|gif|pdf|mp4|xml)$", re.I)


def _same_site(url: str, base: str) -> bool:
    h1 = urlsplit(url).netloc.lower().removeprefix("www.")
    h2 = urlsplit(base).netloc.lower().removeprefix("www.")
    return h1 == h2 or h1.endswith("." + h2)


def article_links(html: str, page_url: str, site, limit: int) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    selectors = [site.selecteurs["liens"]] if site.selecteurs.get("liens") else _GENERIC_LINKS
    links: list[str] = []
    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href")
            if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
                continue
            url = urljoin(page_url, href).split("#")[0]
            path = urlsplit(url).path
            if not _same_site(url, site.base) or _SKIP_PATH.search(path) or path.strip("/") == "":
                continue
            if url.rstrip("/") == page_url.rstrip("/") or url in links:
                continue
            links.append(url)
        if links:          # le premier sélecteur qui donne des liens gagne
            break
    return links[:limit]


def _jsonld_date(soup) -> str | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                if d.get("datePublished"):
                    return d["datePublished"]
                stack.extend(v for v in d.values() if isinstance(v, (dict, list)))
    return None


def _meta(soup, *names) -> str | None:
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n}) \
            or soup.find("meta", attrs={"itemprop": n})
        if tag and tag.get("content"):
            return tag["content"]
    return None


def parse_article(html: str, url: str, site) -> tuple[str, object, str]:
    soup = BeautifulSoup(html, "lxml")
    sel = site.selecteurs or {}
    # titre
    titre = ""
    if sel.get("titre") and soup.select_one(sel["titre"]):
        titre = soup.select_one(sel["titre"]).get_text(" ")
    titre = clean_text(titre or _meta(soup, "og:title") or (soup.h1.get_text(" ") if soup.h1 else "")
                       or (soup.title.get_text() if soup.title else ""))
    # date
    raw = None
    if sel.get("date"):
        t = soup.select_one(sel["date"])
        if t:
            raw = t.get("datetime") or t.get("content") or t.get_text(" ")
    raw = raw or _meta(soup, "article:published_time", "datePublished", "og:published_time") \
        or _jsonld_date(soup)
    if not raw:
        t = soup.find("time")
        raw = t and (t.get("datetime") or t.get_text(" "))
    date = parse_any(raw)
    # contenu
    body = None
    for s in [sel.get("contenu"), "[itemprop=articleBody]", ".entry-content", ".article-content",
              ".post-content", "article"]:
        if s and soup.select_one(s):
            body = soup.select_one(s)
            break
    para = first_paragraph(str(body)) if body else ""
    if not para:
        para = clean_text(_meta(soup, "og:description", "description") or "")
    return titre, date, para


def collect(site, http, start, end, opts, storage=None) -> list[Article]:
    if not site.rubriques:
        raise CollectError("HTML : aucune rubrique configurée")
    limit = opts.get("html_max_articles", 40)
    max_old = opts.get("html_stop_apres_anciens", 5)
    out: list[Article] = []
    errors = []
    pages_ok = 0
    for rub in site.rubriques:
        try:
            r = http.get(rub)
        except Exception as e:
            errors.append(f"{rub} : {e}")
            continue
        pages_ok += 1
        links = article_links(r.text, r.url, site, limit)
        if not links:
            errors.append(f"{rub} : aucun lien d'article trouvé (sélecteur à ajuster ?)")
            continue
        old_streak = 0
        for link in links:
            known = storage.get_article(link) if storage else None
            if known:                            # exécution incrémentale : pas de requête
                art = known
                art.methode = "html"
            else:
                try:
                    page = http.get(link)
                    titre, date, para = parse_article(page.text, link, site)
                except Exception as e:
                    errors.append(f"{link} : {e}")
                    continue
                if not date:
                    log.debug("[%s] date introuvable : %s", site.cle, link)
                    continue
                art = Article(url=link, source=site.cle, source_nom=site.nom,
                              langue=detect_language(titre + " " + para, site.langue),
                              titre=titre, paragraphe=para, date=date, methode="html")
            if art.date < start:
                old_streak += 1
                if old_streak >= max_old:         # la rubrique est triée par date
                    break
                continue
            old_streak = 0
            if art.date <= end:
                out.append(art)
    if pages_ok == 0:
        raise CollectError("HTML indisponible : " + " | ".join(errors[:3]))
    if errors:
        log.info("[%s] HTML : %d erreur(s) mineure(s) : %s", site.cle, len(errors), errors[0])
    return out
