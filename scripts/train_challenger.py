"""Train an independent ESPN-form challenger on a past season and evaluate later.

python -m scripts.train_challenger \
  --train audit-data/train/seai-nba-2025.json \
  --holdout audit-data/holdout/seai-nba-2026.json \
  --output audit-output/seai-nba-trained-challenger.json

This creates ONLY a shadow experiment, never production weights.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.learned_challenger import train_and_compare


def _read(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("La auditoría ESPN no existe o excede el límite")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Auditoría JSON incorrecta")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--holdout", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = train_and_compare(_read(args.train), _read(args.holdout))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n",
                           encoding="utf-8")
    summary = {k:v for k,v in result.items() if k!="model"}
    print("SEAI_TRAINED_CHALLENGER", json.dumps(summary, ensure_ascii=False), flush=True)
    if result["production_enabled"]:
        raise SystemExit("El challenger experimental jamás debe activarse automáticamente")


if __name__ == "__main__":
    main()
