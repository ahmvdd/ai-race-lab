"""Tests du moteur de jeu — aucun appel réseau, Ollama n'a pas besoin de tourner."""

import pytest

from ai_race.engine import DIRECTIONS, GridWorld, manhattan


def make_world():
    return GridWorld(size=5, positions={"A": (0, 0), "B": (4, 4)}, bonus=(2, 2))


class TestMoves:
    def test_valid_move(self):
        w = make_world()
        assert w.apply_move("A", "droite") is True
        assert w.positions["A"] == (1, 0)
        assert w.trails["A"] == ["droite"]

    def test_move_out_of_bounds(self):
        w = make_world()
        assert w.apply_move("A", "haut") is False
        assert w.positions["A"] == (0, 0)
        assert w.trails["A"] == []  # coup invalide non compté dans le trail

    def test_unknown_direction(self):
        w = make_world()
        assert w.apply_move("A", "nord") is False

    def test_all_directions(self):
        w = GridWorld(size=3, positions={"A": (1, 1)}, bonus=(0, 0))
        for d, (dx, dy) in DIRECTIONS.items():
            w.positions["A"] = (1, 1)
            assert w.apply_move("A", d)
            assert w.positions["A"] == (1 + dx, 1 + dy)

    def test_steps_count(self):
        w = make_world()
        w.apply_move("A", "droite")
        w.apply_move("A", "bas")
        w.apply_move("A", "haut")  # valide : (1,1) -> (1,0)
        assert w.steps("A") == 3


class TestWinAndVisibility:
    def test_has_won(self):
        w = make_world()
        assert not w.has_won("A")
        w.positions["A"] = (2, 2)
        assert w.has_won("A")

    def test_bonus_visible_within_radius(self):
        w = make_world()  # A en (0,0), bonus en (2,2)
        assert not w.is_bonus_visible("A", radius=1)
        assert w.is_bonus_visible("A", radius=2)  # Tchebychev max(2,2)=2

    def test_radius_zero_only_on_bonus(self):
        w = make_world()
        assert not w.is_bonus_visible("A", radius=0)
        w.positions["A"] = (2, 2)
        assert w.is_bonus_visible("A", radius=0)


class TestMetrics:
    def test_manhattan(self):
        assert manhattan((0, 0), (2, 3)) == 5

    def test_manhattan_optimal_uses_start_position(self):
        w = make_world()
        w.apply_move("A", "droite")  # bouge, mais l'optimal reste basé sur le départ
        assert w.manhattan_optimal("A") == 4  # (0,0) -> (2,2)
        assert w.manhattan_optimal("B") == 4  # (4,4) -> (2,2)


class TestRenderAndRandom:
    def test_render_shows_agents_and_hides_bonus(self):
        w = make_world()
        view = w.render_ascii("A", radius=1)  # bonus hors de portée
        assert "A" in view and "B" in view and "*" not in view

    def test_render_shows_bonus_when_visible(self):
        w = make_world()
        view = w.render_ascii("A", radius=2)
        assert "*" in view

    def test_random_world_distinct_positions(self):
        w = GridWorld.random(4, seed=42)
        cells = list(w.positions.values()) + [w.bonus]
        assert len(set(cells)) == 3  # A, B et bonus tous distincts

    def test_random_world_reproducible(self):
        w1 = GridWorld.random(6, seed=7)
        w2 = GridWorld.random(6, seed=7)
        assert w1.positions == w2.positions and w1.bonus == w2.bonus

    def test_invalid_size(self):
        with pytest.raises(ValueError):
            GridWorld(size=1, positions={"A": (0, 0)}, bonus=(0, 0))
