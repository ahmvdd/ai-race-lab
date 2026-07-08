"""Tests du parsing des réponses LLM — pas d'appel réseau (parse_move est pur)."""

import pytest

from ai_race.ollama_client import parse_move, parse_move_and_message


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("droite", "droite"),
        ("  HAUT  ", "haut"),
        ("Je vais à gauche !", "gauche"),
        ("Bas.", "bas"),
        ("Je choisis : DROITE", "droite"),
        ("haut puis bas", "haut"),  # premier mot valide retenu
        ("je ne sais pas", None),
        ("", None),
        ("nord", None),
        ("adroitement", None),  # pas de faux positif par sous-chaîne
    ],
)
def test_parse_move(raw, expected):
    assert parse_move(raw) == expected


@pytest.mark.parametrize(
    "raw,expected_move,expected_message",
    [
        ("droite\nJe fonce vers le bonus !", "droite", "Je fonce vers le bonus !"),
        ("droite", "droite", ""),
        ("", None, ""),
        (None, None, ""),
        # coup absent de la 1ère ligne : on le cherche dans tout le texte (fallback)
        ("Bonjour !\nJe vais à gauche.", "gauche", "Je vais à gauche."),
        ("gauche !\nBluff en approche\nSuite du message", "gauche", "Bluff en approche Suite du message"),
    ],
)
def test_parse_move_and_message(raw, expected_move, expected_message):
    move, message = parse_move_and_message(raw)
    assert move == expected_move
    assert message == expected_message
