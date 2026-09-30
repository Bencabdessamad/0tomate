"""Normalisation de texte arabe / français pour la recherche de mots-clés
et le dédoublonnage."""
from __future__ import annotations

import re
import unicodedata

# Tashkeel (harakat, tanwin, shadda, sukun, dagger alif, marques coraniques)
_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭ]")
_TATWEEL = "ـ"
_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"})
_APOS = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'"})
_ARABIC_CHAR = re.compile(r"[؀-ۿ]")
_SPACES = re.compile(r"\s+")


def normalize_arabic(text: str) -> str:
    """Retire tashkeel et tatweel, unifie أ/إ/آ→ا, ى→ي, ة→ه."""
    if not text:
        return ""
    text = _TASHKEEL.sub("", text).replace(_TATWEEL, "")
    return text.translate(_ALEF)


def strip_accents(text: str) -> str:
    """Retire les accents latins (é→e, ç→c) sans toucher aux lettres arabes
    (déjà normalisées par normalize_arabic)."""
    out = []
    for ch in unicodedata.normalize("NFKD", text):
        if unicodedata.combining(ch) and not _ARABIC_CHAR.match(ch):
            continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def normalize_text(text: str, casefold: bool = True) -> str:
    """Normalisation complète : arabe + accents + apostrophes + espaces (+ casse)."""
    if not text:
        return ""
    text = normalize_arabic(text)
    # NFKC d'abord pour décomposer les ligatures/formes de présentation arabes
    text = unicodedata.normalize("NFKC", text)
    text = normalize_arabic(text)
    text = strip_accents(text).translate(_APOS)
    text = _SPACES.sub(" ", text).strip()
    return text.casefold() if casefold else text


_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def title_key(title: str) -> str:
    """Clé de dédoublonnage d'un titre : normalisé, sans ponctuation."""
    t = normalize_text(title)
    t = _PUNCT.sub(" ", t).replace("_", " ")
    return _SPACES.sub(" ", t).strip()


def arabic_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _ARABIC_CHAR.match(c)) / len(letters)


def detect_language(text: str, default: str = "fr") -> str:
    """Détection simple : 'ar' si majorité de lettres arabes, sinon défaut
    (ou 'fr' si le défaut est 'ar' mais que le texte est en alphabet latin)."""
    if not text or not text.strip():
        return default
    r = arabic_ratio(text)
    if r >= 0.4:
        return "ar"
    if r < 0.1:
        return "fr" if default == "ar" else default
    return default
