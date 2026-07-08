"""Appels à l'API Ollama + parsing des réponses. Seul module qui touche au réseau."""

from __future__ import annotations

import time
import unicodedata
from typing import List, Optional

import requests

from .engine import DIRECTIONS

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaError(RuntimeError):
    pass


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def parse_move(raw_text: str) -> Optional[str]:
    """Extrait la première direction valide d'une réponse brute, sinon None.

    Tolère accents, majuscules, ponctuation et texte autour
    (les petits modèles répondent souvent "Je vais à droite !").
    """
    if not raw_text:
        return None
    normalized = _strip_accents(raw_text.lower())
    tokens = "".join(c if c.isalpha() else " " for c in normalized).split()
    lookup = {_strip_accents(d): d for d in DIRECTIONS}
    for token in tokens:
        if token in lookup:
            return lookup[token]
    return None


def parse_move_and_message(raw_text: Optional[str]) -> "tuple[Optional[str], str]":
    """Parse une réponse en mode chat : 1ère ligne = coup, reste = message à l'adversaire.

    Tolérant : si le coup n'est pas trouvé sur la 1ère ligne, on le cherche dans
    tout le texte (petit modèle qui n'a pas respecté le format).
    """
    if not raw_text:
        return None, ""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return None, ""
    move = parse_move(lines[0])
    message = " ".join(lines[1:]).strip()
    if move is None:
        move = parse_move(raw_text)
    return move, message[:240]


def check_ollama(models: List[str], base_url: str = DEFAULT_BASE_URL) -> None:
    """Vérifie qu'Ollama tourne et que les modèles sont pull-és. Échoue avec un message clair."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(
            f"Ollama injoignable sur {base_url}. Lance `ollama serve` puis réessaie. ({exc})"
        ) from exc

    available = {m["name"].split(":")[0] for m in resp.json().get("models", [])}
    available |= {m["name"] for m in resp.json().get("models", [])}
    missing = [m for m in models if m not in available and m.split(":")[0] not in available]
    if missing:
        raise OllamaError(
            f"Modèle(s) non pull-é(s) : {', '.join(missing)}. "
            f"Fais `ollama pull <modele>` puis réessaie. Disponibles : {sorted(available)}"
        )


def get_move(
    model: str,
    system_prompt: str,
    user_prompt: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 120,
    retries: int = 2,
) -> str:
    """Appelle le modèle et retourne la réponse brute (le parsing est séparé)."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.7},
    }
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except (requests.RequestException, KeyError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise OllamaError(f"Échec de l'appel à {model} après {retries + 1} tentatives : {last_exc}")
