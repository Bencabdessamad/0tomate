"""Chargement de keywords.yaml et détection des acteurs dans un texte."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .normalize import normalize_text

_AR = re.compile(r"[؀-ۿ]")
# Proclitiques arabes : conjonction (و/ف) puis préposition (ب/ل/ك)
_AR_PREFIX = r"(?:[وف]?[بلك]?)"


@dataclass
class Actor:
    id: str
    libelle: str
    type: str = "parti"
    parti: str = ""
    couleur: str = "FFFFFF"
    actif: bool = True
    termes: list[str] = field(default_factory=list)
    termes_faibles: list[str] = field(default_factory=list)
    contexte: list[str] = field(default_factory=list)
    sensible_casse: list[str] = field(default_factory=list)


def _term_pattern(term: str, case_sensitive: bool) -> re.Pattern:
    norm = normalize_text(term, casefold=not case_sensitive)
    words = [re.escape(w) for w in re.split(r"[\s\-]+", norm) if w]
    body = r"[\s\-]+".join(words)
    if _AR.search(norm):
        alts = [body]
        # "ال…" précédé de ل s'écrit "لل…" (للأحرار)
        if norm.startswith("ال"):
            alts.append("لل" + r"[\s\-]+".join(words)[2:])
        body = f"(?:{_AR_PREFIX}(?:{'|'.join(alts)}))"
    return re.compile(rf"(?<!\w){body}(?!\w)")


@dataclass
class Match:
    actor_ids: list[str]
    terms: list[str]
    by_actor: dict[str, list[str]]


class KeywordMatcher:
    def __init__(self, actors: list[Actor]):
        self.actors = [a for a in actors if a.actif]
        self.all_actors = actors
        self._compiled = []
        for a in self.actors:
            cs = set(a.sensible_casse)
            comp = lambda terms: [(t, _term_pattern(t, t in cs), t in cs) for t in terms]
            self._compiled.append((a, comp(a.termes), comp(a.termes_faibles), comp(a.contexte)))

    @classmethod
    def from_yaml(cls, path: str | Path, only: list[str] | None = None) -> "KeywordMatcher":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        actors = []
        for raw in data.get("acteurs", []):
            raw = dict(raw)
            raw["id"] = str(raw["id"])
            raw.setdefault("libelle", raw["id"])
            for k in ("termes", "termes_faibles", "contexte", "sensible_casse"):
                raw[k] = [str(x) for x in (raw.get(k) or [])]
            actors.append(Actor(**{k: v for k, v in raw.items() if k in Actor.__dataclass_fields__}))
        if only:
            wanted = {o.strip().casefold() for o in only}
            unknown = wanted - {a.id.casefold() for a in actors}
            if unknown:
                raise ValueError(f"Acteur(s) inconnu(s) dans keywords.yaml : {', '.join(sorted(unknown))}")
            for a in actors:
                a.actif = a.actif and a.id.casefold() in wanted
        return cls(actors)

    @property
    def actor_ids(self) -> list[str]:
        return [a.id for a in self.actors]

    def find(self, text: str) -> Match:
        norm_ci = normalize_text(text)
        norm_cs = normalize_text(text, casefold=False)

        def hits(compiled):
            return [t for t, pat, cs in compiled if pat.search(norm_cs if cs else norm_ci)]

        by_actor: dict[str, list[str]] = {}
        for actor, strong, weak, ctx in self._compiled:
            found = hits(strong)
            weak_found = hits(weak)
            if weak_found and (found or hits(ctx)):
                found += weak_found
            if found:
                by_actor[actor.id] = found
        terms: list[str] = []
        for lst in by_actor.values():
            terms += [t for t in lst if t not in terms]
        return Match(list(by_actor), terms, by_actor)
