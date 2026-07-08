"""Écriture des résultats : JSONL (brut) + CSV (tableur)."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

CSV_FIELDS = [
    "episode", "model_a", "model_b", "grid_size", "visibility_radius",
    "memory_depth", "memory_strategy", "first_player", "winner",
    "steps_a", "steps_b", "invalid_responses_a", "invalid_responses_b",
    "manhattan_optimal_a", "manhattan_optimal_b", "efficiency_a", "efficiency_b",
]


def efficiency(steps: int, optimal: int) -> float:
    """Ratio steps réels / distance optimale. 1.0 = trajet parfait. inf si optimal=0 évité."""
    return round(steps / max(optimal, 1), 3)


class SessionLogger:
    """Un fichier logs/session_<timestamp>.jsonl + export CSV en fin de session."""

    def __init__(self, log_dir: str = "logs", session_name: str | None = None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        name = session_name or datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.jsonl_path = self.log_dir / f"{name}.jsonl"
        self.csv_path = self.log_dir / f"{name}.csv"

    def log_episode(self, record: Dict) -> None:
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def export_csv(self) -> Path:
        records = load_jsonl(self.jsonl_path)
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                row = dict(r)
                row["efficiency_a"] = efficiency(r["steps_a"], r["manhattan_optimal_a"])
                row["efficiency_b"] = efficiency(r["steps_b"], r["manhattan_optimal_b"])
                writer.writerow(row)
        return self.csv_path


def load_jsonl(path: str | Path) -> List[Dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
