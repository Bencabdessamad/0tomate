"""Dédoublonnage : par URL canonique puis par titre normalisé (dépêches MAP
reprises par plusieurs sites, titres quasi identiques)."""
from __future__ import annotations

from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .normalize import title_key

_TRACKING = ("utm_", "fbclid", "gclid", "amp", "ref", "output")


def canonical_url(url: str) -> str:
    """https, hôte sans www, sans fragment, sans paramètres de suivi,
    sans / final, sans suffixe /amp."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path or "/"
    if path.endswith("/amp/") or path.endswith("/amp"):
        path = path[: path.rfind("/amp")]
    path = path.rstrip("/") or "/"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(_TRACKING)]
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def similar(a: str, b: str, threshold: float = 0.9) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 20:
        return False
    # filtre rapide sur la longueur avant SequenceMatcher
    if abs(len(a) - len(b)) > (1 - threshold) * max(len(a), len(b)) * 2:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def deduplicate(articles, threshold: float = 0.9):
    """Garde la première publication (la plus ancienne) de chaque groupe de
    doublons et note les autres sources dans `reprises`. Retourne
    (articles_uniques, nb_doublons_supprimés)."""
    seen_urls: set[str] = set()
    kept = []
    keys: list[str] = []
    removed = 0
    for art in sorted(articles, key=lambda a: a.date):
        cu = canonical_url(art.url)
        if cu in seen_urls:
            removed += 1
            continue
        seen_urls.add(cu)
        key = title_key(art.titre)
        dup_of = None
        for i, k in enumerate(keys):
            if similar(key, k, threshold):
                dup_of = kept[i]
                break
        if dup_of is not None:
            if art.source_nom != dup_of.source_nom and art.source_nom not in dup_of.reprises:
                dup_of.reprises.append(art.source_nom)
            removed += 1
            continue
        kept.append(art)
        keys.append(key)
    return kept, removed
