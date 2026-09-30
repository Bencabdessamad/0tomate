from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SiteConfig:
    cle: str
    nom: str
    url: str
    langue: str = "ar"
    actif: bool = True
    a_confirmer: bool = False
    methode_preferee: str = "rest"
    rss: list[str] = field(default_factory=list)
    rubriques: list[str] = field(default_factory=list)
    selecteurs: dict = field(default_factory=dict)
    rest_categories: list[int] = field(default_factory=list)
    note: str = ""

    @property
    def base(self) -> str:
        return self.url.rstrip("/")


class CollectError(Exception):
    """Échec d'une méthode de collecte (on passe à la suivante)."""


@dataclass
class SiteReport:
    cle: str
    nom: str
    url: str
    langue: str
    a_confirmer: bool = False
    methode_preferee: str = ""
    methode_utilisee: str = ""
    statuts: dict = field(default_factory=dict)   # methode -> "OK (n)" / "échec : …" / "non tenté"
    trouves: int = 0          # articles dans la fenêtre renvoyés par la collecte
    nouveaux: int = 0         # jamais vus dans la base
    retenus: int = 0          # après filtre mots-clés + dédoublonnage
    erreurs: list[str] = field(default_factory=list)
    duree: float = 0.0
    requetes: int = 0
    bloque: bool = False

    @property
    def etat(self) -> str:
        if self.methode_utilisee:
            return "OK"
        return "BLOQUÉ" if self.bloque else "ÉCHEC"
