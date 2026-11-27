"""Temporal Platt calibration experiment from GitHub Actions ESPN audit artifacts.

Example:
  python -m scripts.calibrate_seai \
    --train audit-2025/seai-nba-2025.json \
    --holdout audit-2026/seai-nba-2026.json \
    --output audit-output/seai-nba-calibration.json

Reads raw prediction/outcome details; never uses Covers or odds prices.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.model_calibration import evaluate_calibration


def load_report(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("Archivo de auditoría inexistente o demasiado grande")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Formato de auditoría incorrecto")
    return obj


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=Path("audit-output/seai-calibration-experiment.json"))
    args = parser.parse_args()
    experiment = evaluate_calibration(
        load_report(args.train), load_report(args.holdout))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(experiment, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(experiment, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
