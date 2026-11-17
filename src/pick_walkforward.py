"""Chronological, source-traceable evaluation of the independent SEAI picks.

A walk-forward evaluation uses each game's target date as the history cutoff.
No model parameter is fitted here; these are descriptive observed diagnostics,
not evidence of calibrated probabilities or positive expected value.
"""
from __future__ import annotations

from datetime import date
from math import isfinite

from .independent_picks import VERSION, predict_from_results


def _number(raw: object) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if isfinite(value) and 0 <= value <= 300 else None


def walkforward(fixtures: list[dict], histories: dict[tuple[str, str], dict],
                *, minimum_evaluated: int = 100,
                minimum_candidates: int = 30) -> dict:
    """Evaluate completed ESPN fixtures without changing a model on the test set.

    fixtures: normalized ESPNs (local_date, sport, away/home names & IDs,
    away_score, home_score, status), potentially from many distinct dates.
    histories: ESPN team schedules for the season, which may include FUTURE
    results; predict_from_results filters by each target date automatically.
    """
    if minimum_evaluated < 1 or minimum_candidates < 1:
        raise ValueError("Minimum sample size must be positive")
    chronological = []
    seen = set()
    for game in fixtures:
        if not isinstance(game, dict) or game.get("sport") not in ("NBA", "NFL", "NHL"):
            continue
        state = str(game.get("status", "")).upper()
        if state not in ("POST", "FINAL"):
            continue
        try:
            target = game["local_date"]
            target = target if isinstance(target, date) else date.fromisoformat(str(target))
            away_id = str(game["away_team_id"])
            home_id = str(game["home_team_id"])
            key = (game["sport"], str(game["event_id"]))
            away_score, home_score = _number(game.get("away_score")), _number(game.get("home_score"))
        except (KeyError, ValueError, TypeError):
            continue
        if (key in seen or not away_id.isdecimal() or not home_id.isdecimal()
                or away_score is None or home_score is None or away_score == home_score):
            continue
        seen.add(key)
        chronological.append((target, key, game, away_id, home_id, away_score, home_score))
    chronological.sort(key=lambda row: (row[0], row[1]))

    evaluated = []
    for target, _, game, away_id, home_id, away_score, home_score in chronological:
        away_history = histories.get((game["sport"], away_id))
        home_history = histories.get((game["sport"], home_id))
        if not away_history or not home_history:
            continue
        signal = predict_from_results(
            game["sport"], game.get("away", ""), game.get("home", ""),
            away_history, home_history, target
        )
        if signal.get("status") not in {"PASAR", "CANDIDATO_EXPERIMENTAL"}:
            continue
        chosen = signal["status"] == "CANDIDATO_EXPERIMENTAL"
        actual_home = home_score > away_score
        correct = (signal["side"] == ("local" if actual_home else "visitante"))
        p_home = signal["probability_home_experimental"]
        evaluated.append({
            "date": target.isoformat(), "sport": game["sport"],
            "event_id": str(game["event_id"]),
            "status": signal["status"], "selected": signal["team"] if chosen else None,
            "actual_winner": game["home"] if actual_home else game["away"],
            "correct": correct if chosen else None,
            "p_home_experimental": p_home,
            "brier": round((p_home - float(actual_home)) ** 2, 6),
            "away_games": signal["away_games"], "home_games": signal["home_games"],
            "model": VERSION,
        })
    candidates = [row for row in evaluated if row["selected"]]
    n, k = len(evaluated), len(candidates)
    wins = sum(row["correct"] for row in candidates)
    coverage = k / n if n else None
    accuracy = wins / k if k else None
    brier = sum(row["brier"] for row in evaluated) / n if n else None
    # A constant 50/50 forecast has Brier=.25 on every non-tie event.
    # Comparing to 0.25 is just one diagnostic, not proof of profitable odds.
    enough = n >= minimum_evaluated and k >= minimum_candidates
    return {
        "version": VERSION,
        "evaluation": "WALK_FORWARD_SIN_REENTRENAMIENTO",
        "validation_status": "AUDITORIA_DESCRIPTIVA" if enough else "MUESTRA_INSUFICIENTE",
        "fixture_count": len(chronological),
        "evaluated_count": n,
        "candidate_count": k,
        "passed_count": n-k,
        "correct_candidates": wins,
        "candidate_accuracy_observed": round(accuracy, 5) if accuracy is not None else None,
        "candidate_coverage": round(coverage, 5) if coverage is not None else None,
        "brier_all_evaluated": round(brier, 6) if brier is not None else None,
        "brier_50_50_reference": 0.25,
        "minimum_evaluated": minimum_evaluated,
        "minimum_candidates": minimum_candidates,
        "model_calibrated": False,
        "model_validated": False,
        "stake_recommended": False,
        "notes": ("Sin lookahead: cada corte ocurre antes de la fecha del encuentro. "
                  "Métricas observadas sobre la muestra, no rentabilidad ni EV."),
        "details": evaluated,
    }
