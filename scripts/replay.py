"""Rejoue une session dans le navigateur, sans avoir à glisser de fichier.

Usage :
    python scripts/replay.py                        # session la plus récente dans logs/
    python scripts/replay.py logs/session_XXXX.jsonl
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_race.replay_server import ReplayServer  # noqa: E402


def latest_session(log_dir: Path) -> Path:
    files = sorted(log_dir.glob("session_*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not files:
        sys.exit(f"Aucun fichier session_*.jsonl trouvé dans {log_dir}")
    return files[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Rejoue une session AI Race Lab dans le navigateur")
    parser.add_argument("session", nargs="?", help="chemin vers un session_*.jsonl (défaut : le plus récent)")
    parser.add_argument("--log-dir", default="logs")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    session_path = Path(args.session) if args.session else latest_session(Path(args.log_dir))
    if not session_path.exists():
        sys.exit(f"Fichier introuvable : {session_path}")

    server = ReplayServer(session_path, port=args.port)
    server.start()
    print(f"Replay de {session_path} : {server.url}")
    webbrowser.open(server.url)
    try:
        input("Entrée pour arrêter le serveur...\n")
    except (EOFError, KeyboardInterrupt):
        pass
    server.stop()


if __name__ == "__main__":
    main()
