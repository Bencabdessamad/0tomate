"""Appel minimal à l'API Anthropic renvoyant du JSON."""
from __future__ import annotations

import json
import logging
import os
import re

log = logging.getLogger("veille.llm")

DEFAULT_MODEL = os.environ.get("VEILLE_MODELE", "claude-haiku-4-5-20251001")


def api_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        log.warning("ANTHROPIC_API_KEY défini mais le paquet `anthropic` n'est pas installé")
        return False
    return True


_client = None


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(max_retries=3, timeout=120.0)
    return _client


def parse_json_array(text: str) -> list:
    """Extrait le premier tableau JSON d'une réponse (tolère ```json … ```)."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < start:
        raise ValueError("pas de tableau JSON dans la réponse")
    return json.loads(text[start:end + 1])


def ask_json(system: str, payload, model: str = DEFAULT_MODEL, max_tokens: int = 8000) -> list:
    import anthropic
    try:
        resp = client().messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
    except anthropic.AuthenticationError as e:
        raise RuntimeError("clé ANTHROPIC_API_KEY invalide") from e
    except anthropic.RateLimitError as e:
        raise RuntimeError("limite de débit Anthropic atteinte") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"erreur API Anthropic {e.status_code} : {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError("API Anthropic injoignable (réseau)") from e
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("réponse tronquée (max_tokens) : réduire la taille des lots")
    text = "".join(b.text for b in resp.content if b.type == "text")
    return parse_json_array(text)
