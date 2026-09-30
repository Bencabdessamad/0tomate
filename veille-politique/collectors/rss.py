"""Collecte via flux RSS/Atom (feedparser)."""
from __future__ import annotations

import logging

import feedparser

from core.dates import from_struct_utc, parse_any
from core.extract import clean_text, first_paragraph, strip_html
from core.models import Article
from core.normalize import detect_language

from .base import CollectError

log = logging.getLogger("veille.rss")


def feed_urls(site) -> list[str]:
    return site.rss or [f"{site.base}/feed/", f"{site.base}/rss"]


def collect(site, http, start, end, opts) -> list[Article]:
    errors = []
    for feed_url in feed_urls(site):
        try:
            r = http.get(feed_url)
        except Exception as e:
            errors.append(f"{feed_url} : {e}")
            continue
        feed = feedparser.parse(r.content)
        if not feed.entries:
            errors.append(f"{feed_url} : flux vide ou invalide")
            continue
        out, oldest = [], None
        for e in feed.entries:
            date = (from_struct_utc(e.get("published_parsed")) or from_struct_utc(e.get("updated_parsed"))
                    or parse_any(e.get("published") or e.get("updated")))
            link = e.get("link")
            if not date or not link:
                continue
            oldest = date if oldest is None else min(oldest, date)
            if not (start <= date <= end):
                continue
            titre = clean_text(strip_html(e.get("title", "")))
            html = ""
            if e.get("content"):
                html = e["content"][0].get("value", "")
            para = first_paragraph(html) or first_paragraph(e.get("summary", ""))
            out.append(Article(url=link, source=site.cle, source_nom=site.nom,
                               langue=detect_language(titre + " " + para, site.langue),
                               titre=titre, paragraphe=para, date=date, methode="rss"))
        if oldest and oldest > start:
            log.warning("[%s] le flux RSS ne remonte qu'au %s : la fenêtre demandée n'est peut-être "
                        "pas couverte entièrement", site.cle, oldest.strftime("%d/%m %H:%M"))
        return out
    raise CollectError("RSS indisponible : " + " | ".join(errors))
