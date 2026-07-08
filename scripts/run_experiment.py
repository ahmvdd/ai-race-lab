"""CLI de lancement d'une session AI Race Lab.

Usage :
    python scripts/run_experiment.py --model-a llama3.2 --model-b phi3 --episodes 6
    python scripts/run_experiment.py --grid-size 8 --visibility 1 --memory-strategy conseil
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
    return p


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

    def on_episode(record):
        logger.log_episode(record)
        w = record["winner"] or "nul"
        print(f"  Épisode {record['episode']}: vainqueur={w} "
              f"(A: {record['steps_a']} coups / opt {record['manhattan_optimal_a']}, "
              f"B: {record['steps_b']} coups / opt {record['manhattan_optimal_b']}, "
              f"invalides A/B: {record['invalid_responses_a']}/{record['invalid_responses_b']})")

    on_move = None
    if args.watch:
        def on_move(world, agent, episode_index, message):
            print("\033c", end="")
            print(f"Épisode {episode_index + 1}/{cfg.episodes} — "
                  f"{cfg.model_a} (A) vs {cfg.model_b} (B) — grille {cfg.grid_size}x{cfg.grid_size}\n")
            print(world.render_full())
            print(f"\nA : {world.steps('A')} coup(s) — B : {world.steps('B')} coup(s) "
                  f"— dernier à jouer : {agent}")
            if message:
                print(f'{agent} dit : "{message}"')
            time.sleep(args.watch_delay)

    run_session(cfg, on_episode=on_episode, on_move=on_move)
    csv_path = logger.export_csv()
    print(f"\nTerminé. JSONL : {logger.jsonl_path}\nCSV : {csv_path}")
    print(f"Analyse : python analysis/plot_results.py {logger.jsonl_path}")


if __name__ == "__main__":
    main()
