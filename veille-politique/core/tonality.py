"""Tonalité (positive / neutre / négative) de chaque article vis-à-vis des
acteurs détectés, via Claude. Sans clé API, la colonne reste vide."""
from __future__ import annotations

import hashlib
import logging

from . import llm

log = logging.getLogger("veille.tonalite")

LABELS = ("positive", "neutre", "négative")
SYSTEM = (
    "Tu analyses la presse politique marocaine pour une cellule de veille. Pour chaque article "
    "(titre + premier paragraphe), indique la tonalité envers les acteurs politiques listés dans "
    "\"acteurs\" : \"positive\" (valorisant, succès, soutien), \"négative\" (critique, accusation, "
    "échec, polémique) ou \"neutre\" (factuel, agenda, déclaration sans jugement). En cas de doute : "
    "\"neutre\". Entrée : tableau JSON d'objets {\"id\", \"titre\", \"texte\", \"acteurs\"}. "
    "Sortie : UNIQUEMENT un tableau JSON d'objets {\"id\", \"tonalite\"}."
)


def _key(a) -> str:
    raw = "|".join([a.titre, a.paragraphe, ",".join(sorted(a.acteurs))])
    return hashlib.sha256(raw.encode()).hexdigest()


def _norm_label(v: str) -> str:
    v = (v or "").strip().lower()
    if v.startswith("pos"):
        return "positive"
    if v.startswith(("nég", "neg")):
        return "négative"
    if v.startswith("neu"):
        return "neutre"
    return ""


def classify(articles, storage, batch_size: int = 15) -> int:
    todo = []
    for a in articles:
        cached = storage.get_tonality(_key(a))
        if cached is not None:
            a.tonalite = cached
        else:
            todo.append(a)
    if not todo:
        return 0
    if not llm.api_available():
        log.info("Tonalité : pas de clé ANTHROPIC_API_KEY, colonne laissée vide")
        return 0
    done = 0
    for b in range(0, len(todo), batch_size):
        batch = todo[b:b + batch_size]
        payload = [{"id": i, "titre": a.titre_trad or a.titre, "texte": a.paragraphe_trad or a.paragraphe,
                    "acteurs": a.acteurs} for i, a in enumerate(batch)]
        try:
            res = llm.ask_json(SYSTEM, payload, max_tokens=2000)
        except Exception as e:
            log.warning("Tonalité en échec pour un lot (%s)", e)
            continue
        by_id = {int(r["id"]): _norm_label(str(r.get("tonalite", ""))) for r in res if "id" in r}
        for i, a in enumerate(batch):
            if by_id.get(i):
                a.tonalite = by_id[i]
                storage.put_tonality(_key(a), a.tonalite, llm.DEFAULT_MODEL)
                done += 1
    log.info("Tonalité : %d article(s) classé(s) via Claude", done)
    return done
