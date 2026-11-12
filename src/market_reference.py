"""Comparaciones contra cuotas de otras casas; NO predicciones independientes."""
from __future__ import annotations
from collections import defaultdict
from statistics import mean
from .math_utils import implied_probability, expected_roi, american_to_decimal, no_vig_probabilities


def build_market_rows(events: list[dict]) -> list[dict]:
    rows = []
    for event in events:
        books = []
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                try:
                    odds = {o["name"]: float(o["price"]) for o in market["outcomes"]}
                    if len(odds) < 2 or 0 in odds.values():
                        continue
                    fair = no_vig_probabilities(odds)
                except (KeyError, ValueError, TypeError):
                    continue
                books.append((bookmaker.get("key", ""), bookmaker.get("title", ""),
                              market.get("last_update", bookmaker.get("last_update", "")), odds, fair))
        for book_key, book_name, updated, odds, fair in books:
            for outcome, american in odds.items():
                peers = [b[4][outcome] for b in books
                         if b[0] != book_key and set(b[3]) == set(odds) and outcome in b[4]]
                ref = mean(peers) if len(peers) >= 2 else None
                # REFERENCE ONLY; NO es edge inferido por un modelo predictivo.
                rows.append({
                    "sport": event.get("_sport_name", event.get("sport_key", "")),
                    "event_id": event.get("id", ""),
                    "start_utc": event.get("commence_time", ""),
                    "event": f'{event.get("away_team", "")} vs {event.get("home_team", "")}',
                    "market": "h2h",
                    "outcome": outcome,
                    "book_key": book_key,
                    "bookmaker": book_name,
                    "odds_american": american,
                    "odds_decimal": round(american_to_decimal(american), 4),
                    "book_implied_prob": round(implied_probability(american), 6),
                    "book_no_vig_prob": round(fair[outcome], 6),
                    "peer_reference_prob": round(ref, 6) if ref is not None else "",
                    "peer_count": len(peers),
                    "reference_ev": round(expected_roi(american_to_decimal(american), ref), 6)
                                    if ref is not None else "",
                    "odds_updated_utc": updated,
                    "model_status": "MERCADO_SIN_MODELO_INDEPENDIENTE",
                    "recommendation": "SIN_RECOMENDACION",
                })
    return rows
