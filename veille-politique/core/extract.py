"""Extraction du premier paragraphe utile d'un contenu HTML d'article,
en ignorant légendes, publicités, encadrés "lire aussi", crédits photo…"""
from __future__ import annotations

import html as htmllib
import re

from bs4 import BeautifulSoup, Tag

# Balises jamais porteuses du chapô
_DROP_TAGS = ["script", "style", "noscript", "iframe", "figure", "figcaption",
              "aside", "form", "button", "svg", "video", "audio", "ins", "table"]
# Classes / id typiques de pubs, légendes, partages, encadrés
_NOISE = re.compile(
    r"(^|[\s_-])(ad|ads|adv|advert|advertisement|pub|publicite|sponsor|sponsored|banner|"
    r"caption|wp-caption|legend|credit|share|sharing|social|related|read-?more|"
    r"lire-aussi|newsletter|tags?|breadcrumb|author|byline|meta|comments?)([\s_-]|$)",
    re.I,
)
# Débuts de paragraphes à ignorer (encadrés, crédits)
_SKIP_START = re.compile(
    r"^\s*(اقرأ أيضا|اقرأ ايضا|إقرأ أيضا|اقرأ كذلك|شاهد أيضا|المصدر\s*:|صورة\s*:|الصورة\s*:|"
    r"lire aussi|à lire aussi|voir aussi|lire également|photo\s*:|crédit|©|source\s*:|"
    r"read also|advertisement|publicité)",
    re.I,
)
MIN_LEN = 40


def clean_text(text: str) -> str:
    text = htmllib.unescape(text or "")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _is_noise(tag: Tag) -> bool:
    for el in [tag, *tag.parents]:
        if not isinstance(el, Tag) or el.name in ("body", "html", "[document]"):
            break
        attrs = " ".join(el.get("class") or []) + " " + (el.get("id") or "")
        if attrs.strip() and _NOISE.search(attrs):
            return True
    return False


def first_paragraph(html: str, min_len: int = MIN_LEN) -> str:
    """Premier paragraphe "éditorial" d'un fragment HTML (content.rendered,
    corps d'article, description RSS). Repli : texte brut tronqué."""
    if not html:
        return ""
    if "<" not in html:
        return clean_text(html)
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all(_DROP_TAGS):
        t.decompose()
    candidates = soup.find_all("p") or []
    for p in candidates:
        if _is_noise(p):
            continue
        text = clean_text(p.get_text(" "))
        if len(text) < min_len or _SKIP_START.match(text):
            continue
        # paragraphe composé uniquement d'un lien (encadré "à lire")
        links = "".join(a.get_text(" ") for a in p.find_all("a"))
        if links and len(clean_text(links)) >= 0.9 * len(text):
            continue
        return text
    # Pas de <p> exploitable : texte brut
    text = clean_text(soup.get_text(" "))
    if _SKIP_START.match(text):
        return ""
    return text[:600]


def strip_html(html: str) -> str:
    if not html:
        return ""
    if "<" not in html:
        return clean_text(html)
    return clean_text(BeautifulSoup(html, "lxml").get_text(" "))
