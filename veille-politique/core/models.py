from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    url: str
    source: str               # clé du site (sites.yaml)
    source_nom: str
    langue: str               # ar | fr
    titre: str
    paragraphe: str
    date: datetime            # aware, Africa/Casablanca
    methode: str = ""         # rest | rss | html
    # remplis après filtrage
    acteurs: list[str] = field(default_factory=list)
    mots_cles: list[str] = field(default_factory=list)
    titre_trad: str = ""
    paragraphe_trad: str = ""
    tonalite: str = ""
    reprises: list[str] = field(default_factory=list)   # autres sources (doublons)
    nouveau: bool = True
