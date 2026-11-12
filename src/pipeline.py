"""Genera CSV que Excel puede abrir. --mode live requiere API de cuotas."""
from __future__ import annotations
import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .odds_api import fetch_live_events, OddsAPIError
from .market_reference import build_market_rows

FIELDS = ["sport", "event_id", "start_utc", "event", "market", "outcome", "book_key",
          "bookmaker", "odds_american", "odds_decimal", "book_implied_prob",
          "book_no_vig_prob", "peer_reference_prob", "peer_count", "reference_ev",
          "odds_updated_utc", "model_status", "recommendation"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("demo", "live"), default="demo")
    parser.add_argument("--output", default="output/referencias_mercado.csv")
    parser.add_argument("--region", choices=("us", "us2", "uk", "eu", "au"), default="us")
    args = parser.parse_args()

    if args.mode == "demo":
        source = Path(__file__).resolve().parents[1] / "data" / "eventos_demo.json"
        events = json.loads(source.read_text(encoding="utf-8"))
        selected = ["EVENTOS_FICTICIOS"]
    else:
        events, selected = fetch_live_events(os.environ.get("ODDS_API_KEY", ""), args.region)
        # MVP solo prepartido: no incorporar cuotas de juegos ya iniciados.
        now = datetime.now(timezone.utc)
        future_events = []
        for event in events:
            try:
                begins = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
            except (ValueError, KeyError, TypeError):
                continue
            if begins > now:
                future_events.append(event)
        events = future_events

    rows = build_market_rows(events)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "sports_requested": ["NBA", "NFL", "NHL", "TENIS"],
        "provider_sport_keys_queried": selected,
        "rows_written": len(rows),
        "valid_independent_model": False,
        "parlays_enabled": False,
        "note": "Solo referencia cruzada de mercado. No son recomendaciones ni probabilidades validadas.",
    }
    path.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generadas {len(rows)} filas en {path}. Estado: SIN MODELO PREDICTIVO VALIDADO")


if __name__ == "__main__":
    main()
