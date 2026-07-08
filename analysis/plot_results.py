"""Génère graphes + résumé texte à partir d'un fichier de logs, sans relancer les modèles.

Usage :
    python analysis/plot_results.py logs/session_XXXX.jsonl
    python analysis/plot_results.py logs/session_XXXX.jsonl --out logs/session_XXXX_plots.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")  # pas d'affichage interactif : sortie PNG
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_race.logging_utils import efficiency, load_jsonl  # noqa: E402


def _series(records: List[Dict]) -> Dict:
    episodes = [r["episode"] for r in records]
    data = {"episodes": episodes}
    for key in ("a", "b"):
        data[f"steps_{key}"] = [r[f"steps_{key}"] for r in records]
        # Efficacité seulement sur les épisodes gagnés : le perdant s'arrête quand
        # l'autre trouve le bonus, son nombre de coups est tronqué et n'est pas comparable.
        data[f"eff_{key}"] = [
            efficiency(r[f"steps_{key}"], r[f"manhattan_optimal_{key}"])
            if r["winner"] == key.upper() else None
            for r in records
        ]
        data[f"invalid_{key}"] = [r[f"invalid_responses_{key}"] for r in records]
        wins, cum = [], 0
        for r in records:
            cum += 1 if r["winner"] == key.upper() else 0
            wins.append(cum)
        data[f"cumwins_{key}"] = wins
    return data


def make_plots(records: List[Dict], out_path: Path) -> Path:
    d = _series(records)
    ep = d["episodes"]
    label_a = f"A ({records[0]['model_a']})"
    label_b = f"B ({records[0]['model_b']})"

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("AI Race Lab — progression par épisode", fontsize=14)

    ax = axes[0][0]
    ax.plot(ep, d["steps_a"], "o-", label=label_a)
    ax.plot(ep, d["steps_b"], "s-", label=label_b)
    ax.set_title("Nombre de coups par épisode")
    ax.set_xlabel("Épisode"); ax.set_ylabel("Coups"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[0][1]
    ax.plot(ep, d["eff_a"], "o-", label=label_a)
    ax.plot(ep, d["eff_b"], "s-", label=label_b)
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1, label="optimal (1.0)")
    ax.set_title("Ratio d'efficacité — épisodes gagnés uniquement")
    ax.set_xlabel("Épisode"); ax.set_ylabel("Ratio"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1][0]
    ax.plot(ep, d["cumwins_a"], "o-", label=label_a)
    ax.plot(ep, d["cumwins_b"], "s-", label=label_b)
    ax.set_title("Victoires cumulées")
    ax.set_xlabel("Épisode"); ax.set_ylabel("Victoires"); ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1][1]
    ax.plot(ep, d["invalid_a"], "o-", label=label_a)
    ax.plot(ep, d["invalid_b"], "s-", label=label_b)
    ax.set_title("Réponses invalides par épisode")
    ax.set_xlabel("Épisode"); ax.set_ylabel("Réponses invalides"); ax.legend(); ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def _trend(values: List[float]) -> str:
    """Variation entre la moyenne des 2 premières et des 2 dernières valeurs."""
    if len(values) < 4:
        return "n/a (moins de 4 épisodes)"
    first = sum(values[:2]) / 2
    last = sum(values[-2:]) / 2
    if first == 0:
        return "n/a"
    pct = (last - first) / first * 100
    return f"{pct:+.0f}% de coups entre les 2 premières et les 2 dernières parties"


def summary(records: List[Dict]) -> str:
    d = _series(records)
    n = len(records)
    lines = []
    for key, model_field in (("a", "model_a"), ("b", "model_b")):
        agent = key.upper()
        wins = d[f"cumwins_{key}"][-1]
        effs = [e for e in d[f"eff_{key}"] if e is not None]
        eff_txt = f"efficacité moyenne {sum(effs) / len(effs):.2f}x (sur épisodes gagnés)" \
            if effs else "efficacité n/a (aucune victoire)"
        total_invalid = sum(d[f"invalid_{key}"])
        lines.append(
            f"Modèle {agent} ({records[0][model_field]}) : {wins} victoire(s)/{n}, "
            f"{eff_txt}, {total_invalid} réponse(s) invalide(s), "
            f"tendance {_trend(d[f'steps_{key}'])}"
        )
    draws = sum(1 for r in records if r["winner"] is None)
    if draws:
        lines.append(f"Matchs nuls (plafond de coups atteint) : {draws}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse d'une session AI Race Lab")
    parser.add_argument("logfile", help="Fichier .jsonl produit par run_experiment.py")
    parser.add_argument("--out", help="Chemin du PNG de sortie (défaut : <logfile>_plots.png)")
    args = parser.parse_args()

    log_path = Path(args.logfile)
    records = load_jsonl(log_path)
    if not records:
        sys.exit(f"Aucun épisode dans {log_path}")

    out_path = Path(args.out) if args.out else log_path.with_suffix("").parent / (
        log_path.stem + "_plots.png"
    )
    make_plots(records, out_path)
    print(f"Graphes : {out_path}\n")
    print(summary(records))


if __name__ == "__main__":
    main()
