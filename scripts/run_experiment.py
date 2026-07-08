"""CLI de lancement d'une session AI Race Lab.

Usage :
    python scripts/run_experiment.py --model-a llama3.2 --model-b phi3 --episodes 6
    python scripts/run_experiment.py --grid-size 8 --visibility 1 --memory-strategy conseil
"""

from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_race.live_server import LiveServer  # noqa: E402
from ai_race.logging_utils import SessionLogger  # noqa: E402
from ai_race.memory import STRATEGIES  # noqa: E402
from ai_race.ollama_client import DEFAULT_BASE_URL, OllamaError, check_ollama  # noqa: E402
from ai_race.runner import ExperimentConfig, run_session  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Course de LLM sur grille (Ollama)")
    p.add_argument("--model-a", default="llama3.2")
    p.add_argument("--model-b", default="phi3")
    p.add_argument("--grid-size", type=int, default=6)
    p.add_argument("--visibility", type=int, default=2, help="rayon de visibilité du bonus")
    p.add_argument("--episodes", type=int, default=6)
    p.add_argument("--memory-depth", type=int, default=3,
                   help="nombre de parties précédentes résumées dans le prompt (0 = pas de mémoire)")
    p.add_argument("--memory-strategy", choices=STRATEGIES, default="brut")
    p.add_argument("--swap-start", action="store_true",
                   help="alterne qui joue en premier à chaque épisode (contrôle du biais d'ordre)")
    p.add_argument("--seed", type=int, default=None, help="graine pour des grilles reproductibles")
    p.add_argument("--chat", action="store_true",
                   help="les agents s'envoient un message court à chaque tour (bluff, moquerie...)")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--log-dir", default="logs")
    p.add_argument("--watch", action="store_true",
                   help="affiche la grille en direct dans le terminal à chaque coup joué")
    p.add_argument("--watch-delay", type=float, default=0.2,
                   help="pause (s) entre deux coups affichés en mode --watch")
    p.add_argument("--web", action="store_true",
                   help="ouvre une page web locale qui affiche la partie en temps réel")
    p.add_argument("--web-port", type=int, default=8765)
    p.add_argument("--web-delay", type=float, default=0.6,
                   help="pause (s) entre deux coups affichés en mode --web")
    return p


def _print_watch_frame(cfg, world, agent, episode_index, message, delay) -> None:
    print("\033c", end="")
    print(f"Épisode {episode_index + 1}/{cfg.episodes} — "
          f"{cfg.model_a} (A) vs {cfg.model_b} (B) — grille {cfg.grid_size}x{cfg.grid_size}\n")
    print(world.render_full())
    print(f"\nA : {world.steps('A')} coup(s) — B : {world.steps('B')} coup(s) "
          f"— dernier à jouer : {agent}")
    if message:
        print(f'{agent} dit : "{message}"')
    time.sleep(delay)


def _make_on_episode(logger, live):
    def on_episode(record):
        logger.log_episode(record)
        w = record["winner"] or "nul"
        print(f"  Épisode {record['episode']}: vainqueur={w} "
              f"(A: {record['steps_a']} coups / opt {record['manhattan_optimal_a']}, "
              f"B: {record['steps_b']} coups / opt {record['manhattan_optimal_b']}, "
              f"invalides A/B: {record['invalid_responses_a']}/{record['invalid_responses_b']})")
        if live:
            live.broadcast({
                "type": "episode_end",
                "episode": record["episode"],
                "winner": record["winner"],
                "steps_a": record["steps_a"],
                "steps_b": record["steps_b"],
                "invalid_responses_a": record["invalid_responses_a"],
                "invalid_responses_b": record["invalid_responses_b"],
            })
    return on_episode


def _make_on_episode_start(cfg, live):
    def on_episode_start(world, episode_index):
        live.broadcast({
            "type": "episode_start",
            "episode": episode_index + 1,
            "episodes_total": cfg.episodes,
            "grid_size": world.size,
            "visibility_radius": cfg.visibility_radius,
            "model_a": cfg.model_a,
            "model_b": cfg.model_b,
            "bonus_position": list(world.bonus),
            "start_a": list(world.start_positions["A"]),
            "start_b": list(world.start_positions["B"]),
        })
    return on_episode_start


def _make_on_move(cfg, args, live):
    def on_move(world, agent, episode_index, message):
        if args.watch:
            _print_watch_frame(cfg, world, agent, episode_index, message, args.watch_delay)
        if live:
            live.broadcast({
                "type": "move",
                "episode": episode_index + 1,
                "agent": agent,
                "direction": world.trails[agent][-1],
                "position": {"A": list(world.positions["A"]), "B": list(world.positions["B"])},
                "message": message,
                "steps_a": world.steps("A"),
                "steps_b": world.steps("B"),
            })
            time.sleep(args.web_delay)
    return on_move


def main() -> None:
    args = build_parser().parse_args()

    try:
        check_ollama([args.model_a, args.model_b], base_url=args.base_url)
    except OllamaError as exc:
        sys.exit(f"ERREUR : {exc}")

    cfg = ExperimentConfig(
        model_a=args.model_a,
        model_b=args.model_b,
        grid_size=args.grid_size,
        visibility_radius=args.visibility,
        episodes=args.episodes,
        memory_depth=args.memory_depth,
        memory_strategy=args.memory_strategy,
        swap_start=args.swap_start,
        seed=args.seed,
        chat=args.chat,
    )

    logger = SessionLogger(log_dir=args.log_dir)
    print(f"Session : {cfg.model_a} (A) vs {cfg.model_b} (B) — "
          f"grille {cfg.grid_size}x{cfg.grid_size}, visibilité {cfg.visibility_radius}, "
          f"{cfg.episodes} épisodes\nLogs : {logger.jsonl_path}\n")

    live = None
    if args.web:
        live = LiveServer(port=args.web_port)
        live.start()
        print(f"Vue en direct : {live.url}")
        webbrowser.open(live.url)
        time.sleep(1.5)  # laisse le temps à l'onglet de charger et se connecter au flux

    run_session(
        cfg,
        on_episode=_make_on_episode(logger, live),
        on_move=_make_on_move(cfg, args, live) if (args.watch or live) else None,
        on_episode_start=_make_on_episode_start(cfg, live) if live else None,
    )
    csv_path = logger.export_csv()
    print(f"\nTerminé. JSONL : {logger.jsonl_path}\nCSV : {csv_path}")
    print(f"Analyse : python analysis/plot_results.py {logger.jsonl_path}")


if __name__ == "__main__":
    main()
