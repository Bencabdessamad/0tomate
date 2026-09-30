"""Collecte via l'API REST WordPress (/wp-json/wp/v2/posts)."""
from __future__ import annotations

import logging
from datetime import timedelta, timezone

from core.dates import parse_any
from core.extract import clean_text, first_paragraph, strip_html
from core.models import Article
from core.normalize import detect_language

from .base import CollectError

log = logging.getLogger("veille.rest")


def collect(site, http, start, end, opts) -> list[Article]:
    per_page = opts.get("rest_par_page", 50)
    max_pages = opts.get("rest_max_pages", 5)
    # marge de 14 h : certains WordPress interprètent `after` dans leur fuseau
    after = (start - timedelta(hours=14)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    params = {"after": after, "per_page": per_page, "orderby": "date", "order": "desc",
              "_fields": "id,date,date_gmt,link,title,excerpt,content"}
    if site.rest_categories:
        params["categories"] = ",".join(str(c) for c in site.rest_categories)
    url = f"{site.base}/wp-json/wp/v2/posts"
    out: list[Article] = []
    page = 1
    while page <= max_pages:
        params["page"] = page
        try:
            r = http.get(url, params=params)
        except Exception as e:
            if page > 1 and "400" in str(e):   # page au-delà de la dernière
                break
            raise CollectError(f"REST indisponible : {e}") from e
        ctype = r.headers.get("Content-Type", "")
        try:
            posts = r.json()
        except ValueError:
            raise CollectError(f"REST : réponse non JSON ({ctype or 'type inconnu'}), "
                               "probablement protection anti-robot ou pas un WordPress")
        if not isinstance(posts, list):
            raise CollectError(f"REST : format inattendu ({str(posts)[:120]})")
        for p in posts:
            raw_date = p.get("date_gmt")
            date = parse_any(raw_date, naive_tz=timezone.utc) if raw_date else parse_any(p.get("date"))
            if not date or not p.get("link"):
                continue
            if not (start <= date <= end):
                continue
            titre = clean_text(strip_html((p.get("title") or {}).get("rendered", "")))
            para = first_paragraph((p.get("content") or {}).get("rendered", ""))
            if not para:
                para = first_paragraph((p.get("excerpt") or {}).get("rendered", ""))
            out.append(Article(url=p["link"], source=site.cle, source_nom=site.nom,
                               langue=detect_language(titre + " " + para, site.langue),
                               titre=titre, paragraphe=para, date=date, methode="rest"))
        total_pages = int(r.headers.get("X-WP-TotalPages", "1") or 1)
        if len(posts) < per_page or page >= total_pages:
            break
        page += 1
    return out
