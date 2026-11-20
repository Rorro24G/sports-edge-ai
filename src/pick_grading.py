"""Propuestas conservadoras para liquidar apuestas Moneyline mediante ESPN.

Solo verifica cuando el evento terminado coincide con ambos equipos, liga y
fecha. No toca la base automáticamente: el usuario debe aprobar el resultado.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from .pick_context import _team_tokens


def _safe_score(value):
    try:
        score = Decimal(str(value))
        return score if score.is_finite() and score >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _match_event(bet: dict, events: list[dict]) -> dict | None:
    # Apuesta debe mencionar dos equipos con una separación clara.
    selection = str(bet.get("event", ""))
    import re
    parts = re.split(r"\s+(?:vs\.?|contra|@)\s+", selection, flags=re.I)
    if len(parts) != 2:
        return None
    first, second = (_team_tokens(p) for p in parts)
    if not first or not second:
        return None
    possible = []
    for game in events:
        if game.get("sport") != bet.get("sport"):
            continue
        if game.get("local_date") is None:
            continue
        day = game["local_date"]
        if hasattr(day, "isoformat"):
            day = day.isoformat()
        if str(day) != bet.get("event_date_cdmx"):
            continue
        away, home = _team_tokens(game.get("away", "")), _team_tokens(game.get("home", ""))
        if ((first & away and second & home) or (first & home and second & away)):
            possible.append(game)
    return possible[0] if len(possible) == 1 else None


def propose_moneyline_results(bets: list[dict], events: list[dict]) -> list[dict]:
    """Return suggestions with ESPN URL; no side effects."""
    proposals = []
    for bet in bets:
        if bet.get("status") != "pendiente":
            continue
        pick = str(bet.get("selection", "")).strip()
        if not pick.lower().endswith(" ml") and not pick.lower().endswith(" moneyline"):
            continue
        game = _match_event(bet, events)
        if not game or game.get("status") not in ("POST", "FINAL"):
            continue
        away_score = _safe_score(game.get("away_score"))
        home_score = _safe_score(game.get("home_score"))
        if away_score is None or home_score is None:
            continue
        if away_score == home_score:
            continue
        winner = game["away"] if away_score > home_score else game["home"]
        loser = game["home"] if away_score > home_score else game["away"]
        pick_name = pick.rsplit(" ", 1)[0] if pick.lower().endswith(" ml") else pick[:-10].strip()
        requested = _team_tokens(pick_name)
        if not requested:
            continue
        if requested <= _team_tokens(winner):
            verdict = "ganado"
        elif requested <= _team_tokens(loser):
            verdict = "perdido"
        else:
            continue
        proposals.append({
            "bet_id": bet["id"],
            "status": verdict,
            "source_url": game.get("source_url"),
            "score": f"{game['away']} {away_score} - {home_score} {game['home']}",
        })
    return proposals
