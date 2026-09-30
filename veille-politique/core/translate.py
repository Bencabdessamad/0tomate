"""Traduction arabe -> français des articles retenus.
Moteur 1 : API Anthropic (lots, JSON). Moteur 2 : deep-translator (Google).
Cache SQLite : un texte n'est jamais traduit deux fois."""
from __future__ import annotations

import hashlib
import logging

from . import llm
from .normalize import normalize_text

log = logging.getLogger("veille.traduction")

SYSTEM = (
    "Tu es traducteur de presse politique marocaine, de l'arabe (ou darija) vers le {lang}. "
    "Traduis fidèlement chaque texte, dans un style journalistique neutre, sans résumer ni commenter. "
    "Noms propres : translittération française usuelle au Maroc (بنكيران→Benkirane, "
    "المنصوري→Mansouri, أخنوش→Akhannouch, نزار بركة→Nizar Baraka, بنعبد الله→Benabdallah, "
    "شوكي→Chouki). Partis : PAM, RNI, PJD, PPS, USFP, Istiqlal. "
    "Entrée : un tableau JSON d'objets {{\"id\", \"texte\"}}. "
    "Sortie : UNIQUEMENT un tableau JSON d'objets {{\"id\", \"traduction\"}}, mêmes id, même ordre."
)
LANG_NAMES = {"fr": "français", "en": "anglais", "es": "espagnol"}


def cache_key(text: str, target: str) -> str:
    return hashlib.sha256(f"{target}|{normalize_text(text, casefold=False)}".encode()).hexdigest()


class Translator:
    def __init__(self, storage, target: str = "fr", batch_size: int = 12, engine: str | None = None):
        self.storage = storage
        self.target = target
        self.batch_size = batch_size
        self.engine = engine or self._pick_engine()
        self.stats = {"cache": 0, "claude": 0, "google": 0, "echecs": 0}

    @staticmethod
    def _pick_engine() -> str | None:
        if llm.api_available():
            return "claude"
        try:
            import deep_translator  # noqa: F401
            return "google"
        except ImportError:
            return None

    # -- moteurs -------------------------------------------------------------
    def _claude(self, texts: list[str]) -> list[str | None]:
        payload = [{"id": i, "texte": t} for i, t in enumerate(texts)]
        res = llm.ask_json(SYSTEM.format(lang=LANG_NAMES.get(self.target, self.target)), payload)
        by_id = {int(r["id"]): str(r.get("traduction", "")).strip() for r in res if "id" in r}
        return [by_id.get(i) or None for i in range(len(texts))]

    def _google(self, texts: list[str]) -> list[str | None]:
        from deep_translator import GoogleTranslator
        tr = GoogleTranslator(source="auto", target=self.target)
        out = []
        for t in texts:
            try:
                out.append(tr.translate(t[:4900]))
            except Exception as e:
                log.debug("deep-translator : %s", e)
                out.append(None)
        return out

    # -- API -----------------------------------------------------------------
    def translate_texts(self, texts: list[str]) -> list[str]:
        result: list[str | None] = [None] * len(texts)
        todo: dict[str, list[int]] = {}
        for i, t in enumerate(texts):
            if not t:
                result[i] = ""
                continue
            k = cache_key(t, self.target)
            cached = self.storage.get_translation(k)
            if cached is not None:
                result[i] = cached
                self.stats["cache"] += 1
            else:
                todo.setdefault(k, []).append(i)
        keys = list(todo)
        for b in range(0, len(keys), self.batch_size):
            batch_keys = keys[b:b + self.batch_size]
            batch = [texts[todo[k][0]] for k in batch_keys]
            translated, engine = self._run_batch(batch)
            for k, src, tr in zip(batch_keys, batch, translated):
                if tr:
                    self.storage.put_translation(k, self.target, src, tr, engine)
                    self.stats[engine] += 1
                else:
                    self.stats["echecs"] += 1
                for i in todo[k]:
                    result[i] = tr or ""
        return [r or "" for r in result]

    def _run_batch(self, batch):
        if self.engine == "claude":
            try:
                return self._claude(batch), "claude"
            except Exception as e:
                log.warning("Traduction Claude en échec (%s) : repli deep-translator", e)
                try:
                    return self._google(batch), "google"
                except ImportError:
                    return [None] * len(batch), "claude"
        if self.engine == "google":
            return self._google(batch), "google"
        return [None] * len(batch), "aucun"

    def translate_articles(self, articles) -> None:
        """Remplit titre_trad / paragraphe_trad pour les articles non français."""
        todo = [a for a in articles if a.langue != self.target]
        if not todo:
            return
        if not self.engine:
            log.warning("Aucun moteur de traduction (ni clé Anthropic, ni deep-translator)")
            return
        texts = []
        for a in todo:
            texts += [a.titre, a.paragraphe]
        out = self.translate_texts(texts)
        for n, a in enumerate(todo):
            a.titre_trad, a.paragraphe_trad = out[2 * n], out[2 * n + 1]
        log.info("Traduction (%s) : %d depuis le cache, %d via Claude, %d via deep-translator, %d échec(s)",
                 self.engine, self.stats["cache"], self.stats["claude"], self.stats["google"],
                 self.stats["echecs"])
