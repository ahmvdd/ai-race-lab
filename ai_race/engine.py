"""Logique de jeu pure : grille, positions, règles.

Aucune dépendance réseau — testable unitairement sans Ollama.
Coordonnées : (x, y), x = colonne (0 à gauche), y = ligne (0 en haut).
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

Position = Tuple[int, int]

# direction -> (dx, dy)
DIRECTIONS: Dict[str, Tuple[int, int]] = {
    "haut": (0, -1),
    "bas": (0, 1),
    "gauche": (-1, 0),
    "droite": (1, 0),
}


def manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class GridWorld:
    """État d'une partie : positions des agents, bonus, historique des coups."""

    def __init__(self, size: int, positions: Dict[str, Position], bonus: Position):
        if size < 2:
            raise ValueError("size doit être >= 2")
        for name, pos in positions.items():
            if not self._in_bounds(pos, size):
                raise ValueError(f"position de {name} hors grille : {pos}")
        if not self._in_bounds(bonus, size):
            raise ValueError(f"bonus hors grille : {bonus}")

        self.size = size
        self.positions: Dict[str, Position] = dict(positions)
        self.start_positions: Dict[str, Position] = dict(positions)
        self.bonus: Position = bonus
        self.trails: Dict[str, List[str]] = {name: [] for name in positions}

    # ------------------------------------------------------------------ #
    @classmethod
    def random(
        cls,
        size: int,
        agents: Tuple[str, ...] = ("A", "B"),
        seed: Optional[int] = None,
    ) -> "GridWorld":
        """Place aléatoirement les agents et le bonus (tous distincts)."""
        rng = random.Random(seed)
        cells = [(x, y) for x in range(size) for y in range(size)]
        picked = rng.sample(cells, len(agents) + 1)
        positions = {name: picked[i] for i, name in enumerate(agents)}
        return cls(size, positions, bonus=picked[-1])

    # ------------------------------------------------------------------ #
    @staticmethod
    def _in_bounds(pos: Position, size: int) -> bool:
        return 0 <= pos[0] < size and 0 <= pos[1] < size

    def apply_move(self, agent: str, direction: str) -> bool:
        """Applique un coup. Retourne False si direction inconnue ou sortie de grille."""
        if direction not in DIRECTIONS:
            return False
        dx, dy = DIRECTIONS[direction]
        x, y = self.positions[agent]
        new_pos = (x + dx, y + dy)
        if not self._in_bounds(new_pos, self.size):
            return False
        self.positions[agent] = new_pos
        self.trails[agent].append(direction)
        return True

    def is_bonus_visible(self, agent: str, radius: int) -> bool:
        """Le bonus est visible si dans un carré de rayon `radius` (distance de Tchebychev)."""
        x, y = self.positions[agent]
        bx, by = self.bonus
        return max(abs(bx - x), abs(by - y)) <= radius

    def has_won(self, agent: str) -> bool:
        return self.positions[agent] == self.bonus

    def steps(self, agent: str) -> int:
        return len(self.trails[agent])

    def manhattan_optimal(self, agent: str) -> int:
        """Distance minimale théorique entre la position de départ et le bonus."""
        return manhattan(self.start_positions[agent], self.bonus)

    def render_full(self) -> str:
        """Vue spectateur : agents et bonus toujours visibles, quel que soit un rayon."""
        rows = []
        for y in range(self.size):
            row = []
            for x in range(self.size):
                cell = "."
                if (x, y) == self.bonus:
                    cell = "*"
                for name, pos in self.positions.items():
                    if pos == (x, y):
                        cell = name
                row.append(cell)
            rows.append(" ".join(row))
        return "\n".join(rows)

    def render_ascii(self, viewer: str, radius: int) -> str:
        """Vue de la grille pour `viewer`.

        Symboles : lettre de l'agent pour chaque agent, '*' pour le bonus
        (uniquement s'il est visible pour le viewer), '.' sinon.
        """
        show_bonus = self.is_bonus_visible(viewer, radius)
        rows = []
        for y in range(self.size):
            row = []
            for x in range(self.size):
                cell = "."
                if show_bonus and (x, y) == self.bonus:
                    cell = "*"
                for name, pos in self.positions.items():
                    if pos == (x, y):
                        cell = name
                row.append(cell)
            rows.append(" ".join(row))
        return "\n".join(rows)
