"""Lance une session et l'affiche en direct dans le navigateur — une seule commande, zéro option.

Usage :
    python scripts/watch.py

Équivalent à `run_experiment.py --web --chat` avec les valeurs par défaut. Toute
option de run_experiment.py reste utilisable si besoin, ex. :
    python scripts/watch.py --episodes 10 --grid-size 8
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_experiment  # noqa: E402

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--web", "--chat", *sys.argv[1:]]
    run_experiment.main()
