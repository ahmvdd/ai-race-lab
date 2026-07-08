"""Tests de l'orchestration avec un faux LLM injecté — Ollama jamais appelé."""

from ai_race.engine import GridWorld
from ai_race.memory import AgentMemory
from ai_race.runner import ExperimentConfig, run_episode, run_session


def greedy_move_fn(model, system_prompt, user_prompt):
    """Faux LLM : lit sa position et la grille dans le prompt et va vers le bonus si visible,
    sinon va vers la droite/bas. Suffisant pour terminer une partie."""
    import re

    pos = re.search(r"colonne (\d+), ligne (\d+)", user_prompt)
    x, y = int(pos.group(1)), int(pos.group(2))
    grid_lines = [l for l in user_prompt.split("\n") if l and all(c in "AB*. " for c in l)]
    for gy, line in enumerate(grid_lines):
        cells = line.split(" ")
        for gx, cell in enumerate(cells):
            if cell == "*":
                if gx > x:
                    return "droite"
                if gx < x:
                    return "gauche"
                if gy > y:
                    return "bas"
                return "haut"
    return "droite" if x < 3 else "bas"


def bad_then_good_fn(model, system_prompt, user_prompt):
    """Répond n'importe quoi une fois sur deux pour tester le comptage d'invalides."""
    bad_then_good_fn.calls = getattr(bad_then_good_fn, "calls", 0) + 1
    if bad_then_good_fn.calls % 2 == 1:
        return "je réfléchis..."
    return greedy_move_fn(model, system_prompt, user_prompt)


def test_run_episode_completes_and_has_schema():
    cfg = ExperimentConfig(episodes=1, grid_size=5, visibility_radius=5, seed=1)
    memories = {a: AgentMemory() for a in ("A", "B")}
    record = run_episode(cfg, 0, memories, get_move_fn=greedy_move_fn)
    for key in ("episode", "winner", "steps_a", "steps_b", "trail_a", "trail_b",
                "invalid_responses_a", "invalid_responses_b", "bonus_position",
                "manhattan_optimal_a", "manhattan_optimal_b"):
        assert key in record
    assert record["winner"] in ("A", "B")


def test_invalid_responses_counted():
    cfg = ExperimentConfig(episodes=1, grid_size=4, visibility_radius=4, seed=2)
    memories = {a: AgentMemory() for a in ("A", "B")}
    record = run_episode(cfg, 0, memories, get_move_fn=bad_then_good_fn)
    assert record["invalid_responses_a"] + record["invalid_responses_b"] > 0
    assert record["winner"] in ("A", "B")  # le coup de secours empêche le blocage


def test_session_memory_accumulates():
    cfg = ExperimentConfig(episodes=3, grid_size=4, visibility_radius=4, seed=3)
    records = run_session(cfg, get_move_fn=greedy_move_fn)
    assert len(records) == 3
    assert [r["episode"] for r in records] == [1, 2, 3]


def test_swap_start_alternates_first_player():
    cfg = ExperimentConfig(episodes=2, grid_size=4, visibility_radius=4,
                           seed=4, swap_start=True)
    records = run_session(cfg, get_move_fn=greedy_move_fn)
    assert records[0]["first_player"] == "A"
    assert records[1]["first_player"] == "B"


def chatty_move_fn(model, system_prompt, user_prompt):
    """Faux LLM en mode chat : joue vers le bonus et signe son message avec son propre nom."""
    move = greedy_move_fn(model, system_prompt, user_prompt)
    agent = "A" if "joueur 'A'" in system_prompt else "B"
    return f"{move}\nSalut, ici {agent} !"


def test_chat_relays_message_to_opponent_next_turn():
    seen_prompts = []

    def spy_fn(model, system_prompt, user_prompt):
        seen_prompts.append((system_prompt, user_prompt))
        return chatty_move_fn(model, system_prompt, user_prompt)

    cfg = ExperimentConfig(episodes=1, grid_size=5, visibility_radius=5, seed=1, chat=True)
    memories = {a: AgentMemory() for a in ("A", "B")}
    record = run_episode(cfg, 0, memories, get_move_fn=spy_fn)

    assert record["messages_a"][0] == "Salut, ici A !"
    # B doit voir le message de A dans son prompt du tour suivant (2ème appel)
    assert 'Message de ton adversaire : "Salut, ici A !"' in seen_prompts[1][1]


def test_no_chat_by_default_keeps_single_word_response():
    cfg = ExperimentConfig(episodes=1, grid_size=5, visibility_radius=5, seed=1)
    memories = {a: AgentMemory() for a in ("A", "B")}
    record = run_episode(cfg, 0, memories, get_move_fn=greedy_move_fn)
    assert record["messages_a"] == []
    assert record["messages_b"] == []


def test_memory_prompt_injected_after_first_episode():
    seen_prompts = []

    def spy_fn(model, system_prompt, user_prompt):
        seen_prompts.append(user_prompt)
        return greedy_move_fn(model, system_prompt, user_prompt)

    cfg = ExperimentConfig(episodes=2, grid_size=4, visibility_radius=4, seed=5)
    run_session(cfg, get_move_fn=spy_fn)
    assert not any("parties précédentes" in p for p in seen_prompts[:2])
    assert any("parties précédentes" in p for p in seen_prompts)
