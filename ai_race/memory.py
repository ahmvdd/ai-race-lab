"""Mémoire injectée par agent : résumé des parties précédentes.

Pas de vrai fine-tuning — on simule l'amélioration "en contexte" en
injectant un résumé des N dernières parties dans le prompt.
"""

from __future__ import annotations

from typing import Dict, List

STRATEGIES = ("brut", "conseil")

_ADVICE = (
    "Conseil : explore la grille de façon systématique (balayage ligne par ligne), "
    "ne reviens pas sur tes pas sans raison, et fonce sur le bonus dès qu'il est visible (*)."
)


class AgentMemory:
    """Accumule les résumés d'épisodes d'un agent et construit le bloc mémoire du prompt."""

    def __init__(self, depth: int = 3, strategy: str = "brut"):
        if strategy not in STRATEGIES:
            raise ValueError(f"strategy doit être dans {STRATEGIES}, reçu : {strategy}")
        self.depth = depth
        self.strategy = strategy
        self.history: List[Dict] = []

    def record(self, episode: int, won: bool, steps: int, optimal: int, invalid: int) -> None:
        self.history.append(
            {
                "episode": episode,
                "won": won,
                "steps": steps,
                "optimal": optimal,
                "invalid": invalid,
            }
        )

    def build_prompt(self) -> str:
        """Bloc texte à injecter dans le prompt. Vide si aucune partie jouée ou depth=0."""
        if self.depth <= 0 or not self.history:
            return ""
        lines = ["Résumé de tes parties précédentes :"]
        for h in self.history[-self.depth :]:
            outcome = "VICTOIRE" if h["won"] else "défaite"
            line = (
                f"- Partie {h['episode']} : {outcome} en {h['steps']} coups "
                f"(minimum théorique : {h['optimal']})"
            )
            if h["invalid"]:
                line += f", {h['invalid']} réponse(s) invalide(s)"
            lines.append(line)
        if self.strategy == "conseil":
            lines.append(_ADVICE)
        return "\n".join(lines)
