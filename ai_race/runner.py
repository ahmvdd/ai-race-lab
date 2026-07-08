"""Orchestration d'un épisode / d'une session.

Ne contient aucune logique de jeu (voir engine.py) ni d'appel réseau direct
(voir ollama_client.py). `get_move_fn` est injectable pour tester sans Ollama.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .engine import DIRECTIONS, GridWorld
from .memory import AgentMemory
from .ollama_client import get_move, parse_move, parse_move_and_message

GetMoveFn = Callable[[str, str, str], str]  # (model, system_prompt, user_prompt) -> raw text

SYSTEM_PROMPT = (
    "Tu joues sur une grille {size}x{size}. Tu es le joueur '{agent}'. "
    "Un bonus '*' est caché sur la grille ; le premier joueur qui l'atteint gagne. "
    "Le bonus n'apparaît sur ta vue que s'il est à portée de ta vision. "
    "Réponds UNIQUEMENT par un seul mot parmi : haut, bas, gauche, droite. "
    "Aucune explication, aucun autre texte."
)

CHAT_SYSTEM_PROMPT = (
    "Tu joues sur une grille {size}x{size}. Tu es le joueur '{agent}'. "
    "Un bonus '*' est caché sur la grille ; le premier joueur qui l'atteint gagne. "
    "Le bonus n'apparaît sur ta vue que s'il est à portée de ta vision. "
    "Réponds sur au plus deux lignes :\n"
    "1) UN SEUL mot parmi : haut, bas, gauche, droite (ton coup, obligatoire).\n"
    "2) Un message court à ton adversaire (optionnel, une phrase) : bluff, "
    "négociation, moquerie, ce que tu veux.\n"
    "Aucune autre ligne, aucune explication."
)


@dataclass
class ExperimentConfig:
    model_a: str = "llama3.2"
    model_b: str = "phi3"
    grid_size: int = 6
    visibility_radius: int = 2
    episodes: int = 6
    memory_depth: int = 3
    memory_strategy: str = "brut"  # "brut" | "conseil"
    swap_start: bool = False  # alterne qui joue en premier à chaque épisode
    seed: Optional[int] = None
    max_turns_factor: int = 3  # plafond = size*size*factor coups par agent
    chat: bool = False  # les agents échangent un message court à chaque tour

    @property
    def models(self) -> Dict[str, str]:
        return {"A": self.model_a, "B": self.model_b}


@dataclass
class SessionState:
    memories: Dict[str, AgentMemory] = field(default_factory=dict)


def _build_user_prompt(
    world: GridWorld, agent: str, radius: int, memory_block: str, opponent_message: str = ""
) -> str:
    x, y = world.positions[agent]
    parts = []
    if memory_block:
        parts.append(memory_block)
    parts.append(f"Grille (tu es '{agent}', '*' = bonus si visible) :\n{world.render_ascii(agent, radius)}")
    parts.append(f"Ta position : colonne {x}, ligne {y} (0,0 en haut à gauche).")
    if world.is_bonus_visible(agent, radius):
        parts.append("Le bonus est visible sur ta vue !")
    if opponent_message:
        parts.append(f'Message de ton adversaire : "{opponent_message}"')
    parts.append("Ton prochain coup ? (haut, bas, gauche ou droite)")
    return "\n\n".join(parts)


# (world, agent qui vient de jouer, episode_index, message envoyé par l'agent ce tour-ci)
OnMoveFn = Callable[[GridWorld, str, int, str], None]


def _fallback_move(world: GridWorld, agent: str, rng: random.Random) -> None:
    """Coup de secours aléatoire valide, pour ne pas bloquer la partie sur une réponse invalide."""
    fallback = [
        d for d in DIRECTIONS
        if world._in_bounds(
            (
                world.positions[agent][0] + DIRECTIONS[d][0],
                world.positions[agent][1] + DIRECTIONS[d][1],
            ),
            world.size,
        )
    ]
    world.apply_move(agent, rng.choice(fallback))


def _take_turn(
    cfg: ExperimentConfig,
    world: GridWorld,
    agent: str,
    memories: Dict[str, AgentMemory],
    fn: GetMoveFn,
    rng: random.Random,
    invalid: Dict[str, int],
    raw_responses: Dict[str, List[str]],
    messages: Dict[str, List[str]],
    last_message: Dict[str, str],
) -> None:
    """Joue le tour d'un agent : prompt, appel modèle, parsing, application du coup."""
    other = "B" if agent == "A" else "A"
    template = CHAT_SYSTEM_PROMPT if cfg.chat else SYSTEM_PROMPT
    system_prompt = template.format(size=cfg.grid_size, agent=agent)
    user_prompt = _build_user_prompt(
        world, agent, cfg.visibility_radius, memories[agent].build_prompt(),
        opponent_message=last_message[agent] if cfg.chat else "",
    )
    raw = fn(cfg.models[agent], system_prompt, user_prompt)
    raw_responses[agent].append(raw.strip() if raw else "")

    if cfg.chat:
        move, message = parse_move_and_message(raw)
        messages[agent].append(message)
        last_message[other] = message
    else:
        move = parse_move(raw)

    if move is None or not world.apply_move(agent, move):
        invalid[agent] += 1
        _fallback_move(world, agent, rng)


def _play_turns(
    cfg: ExperimentConfig,
    world: GridWorld,
    order: List[str],
    memories: Dict[str, AgentMemory],
    fn: GetMoveFn,
    rng: random.Random,
    episode_index: int,
    on_move: Optional[OnMoveFn],
) -> "tuple[Optional[str], Dict[str, int], Dict[str, List[str]], Dict[str, List[str]]]":
    """Joue les tours jusqu'à victoire ou plafond. Retourne (winner, invalid, raw_responses, messages)."""
    invalid: Dict[str, int] = {"A": 0, "B": 0}
    raw_responses: Dict[str, List[str]] = {"A": [], "B": []}
    messages: Dict[str, List[str]] = {"A": [], "B": []}
    last_message: Dict[str, str] = {"A": "", "B": ""}
    max_turns = cfg.grid_size * cfg.grid_size * cfg.max_turns_factor

    for _ in range(max_turns):
        for agent in order:
            _take_turn(cfg, world, agent, memories, fn, rng, invalid, raw_responses, messages, last_message)
            if on_move:
                sent = messages[agent][-1] if cfg.chat and messages[agent] else ""
                on_move(world, agent, episode_index, sent)
            if world.has_won(agent):
                return agent, invalid, raw_responses, messages
    return None, invalid, raw_responses, messages


def _build_record(
    cfg: ExperimentConfig,
    episode_index: int,
    world: GridWorld,
    order: List[str],
    winner: Optional[str],
    invalid: Dict[str, int],
    raw_responses: Dict[str, List[str]],
    messages: Dict[str, List[str]],
) -> Dict:
    return {
        "episode": episode_index + 1,
        "model_a": cfg.model_a,
        "model_b": cfg.model_b,
        "grid_size": cfg.grid_size,
        "visibility_radius": cfg.visibility_radius,
        "memory_depth": cfg.memory_depth,
        "memory_strategy": cfg.memory_strategy,
        "first_player": order[0],
        "winner": winner,  # None = match nul (plafond de coups atteint)
        "steps_a": world.steps("A"),
        "steps_b": world.steps("B"),
        "trail_a": world.trails["A"],
        "trail_b": world.trails["B"],
        "raw_a": raw_responses["A"],
        "raw_b": raw_responses["B"],
        "messages_a": messages["A"],
        "messages_b": messages["B"],
        "invalid_responses_a": invalid["A"],
        "invalid_responses_b": invalid["B"],
        "bonus_position": list(world.bonus),
        "start_a": list(world.start_positions["A"]),
        "start_b": list(world.start_positions["B"]),
        "manhattan_optimal_a": world.manhattan_optimal("A"),
        "manhattan_optimal_b": world.manhattan_optimal("B"),
    }


def run_episode(
    cfg: ExperimentConfig,
    episode_index: int,
    memories: Dict[str, AgentMemory],
    get_move_fn: Optional[GetMoveFn] = None,
    rng: Optional[random.Random] = None,
    on_move: Optional[OnMoveFn] = None,
) -> Dict:
    """Joue un épisode complet et retourne l'enregistrement structuré (voir logging_utils)."""
    fn = get_move_fn or get_move
    rng = rng or random.Random()
    seed = None if cfg.seed is None else cfg.seed + episode_index
    world = GridWorld.random(cfg.grid_size, agents=("A", "B"), seed=seed)

    order = ["A", "B"]
    if cfg.swap_start and episode_index % 2 == 1:
        order = ["B", "A"]

    winner, invalid, raw_responses, messages = _play_turns(
        cfg, world, order, memories, fn, rng, episode_index, on_move
    )
    record = _build_record(cfg, episode_index, world, order, winner, invalid, raw_responses, messages)

    for agent, key in (("A", "a"), ("B", "b")):
        memories[agent].record(
            episode=episode_index + 1,
            won=(winner == agent),
            steps=record[f"steps_{key}"],
            optimal=record[f"manhattan_optimal_{key}"],
            invalid=record[f"invalid_responses_{key}"],
        )
    return record


def run_session(
    cfg: ExperimentConfig,
    get_move_fn: Optional[GetMoveFn] = None,
    on_episode: Optional[Callable[[Dict], None]] = None,
    on_move: Optional[OnMoveFn] = None,
) -> List[Dict]:
    """Joue cfg.episodes épisodes avec mémoire persistante entre les parties."""
    memories = {
        agent: AgentMemory(cfg.memory_depth, cfg.memory_strategy) for agent in ("A", "B")
    }
    rng = random.Random(cfg.seed)
    records = []
    for i in range(cfg.episodes):
        record = run_episode(cfg, i, memories, get_move_fn=get_move_fn, rng=rng, on_move=on_move)
        records.append(record)
        if on_episode:
            on_episode(record)
    return records
