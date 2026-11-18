"""Chronological, source-traceable evaluation of the independent SEAI picks.

A walk-forward evaluation uses each game's target date as the history cutoff.
No model parameter is fitted here; these are descriptive observed diagnostics,
not evidence of calibrated probabilities or positive expected value.
"""
from __future__ import annotations

from datetime import date
from math import isfinite, sqrt

from .independent_picks import VERSION, predict_from_results


def _number(raw: object) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if isfinite(value) and 0 <= value <= 300 else None


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval: observed accuracy uncertainty, NOT model calibration."""
    if n < 1 or successes < 0 or successes > n:
        return None
    p = successes / n
    z2 = z * z
    center = (p + z2/(2*n)) / (1+z2/n)
    half = z*sqrt(p*(1-p)/n+z2/(4*n*n))/(1+z2/n)
    return round(max(0.0, center-half), 5), round(min(1.0, center+half), 5)


def calibration_bins(rows: list[dict]) -> list[dict]:
    """Observed home win rates, equal-width bins, no in-sample adjustment."""
    groups = [{"n": 0, "pred_sum": 0., "win_sum": 0.} for _ in range(5)]
    for row in rows:
        p = row["p_home_experimental"]
        index = min(4, int(p*5))
        bucket = groups[index]
        bucket["n"] += 1
        bucket["pred_sum"] += p
        bucket["win_sum"] += int(row["actual_home"])
    return [{
        "range": f"{i*20}-{(i+1)*20}%",
        "n": bucket["n"],
        "avg_predicted_home": round(bucket["pred_sum"]/bucket["n"], 4) if bucket["n"] else None,
        "actual_home_frequency": round(bucket["win_sum"]/bucket["n"], 4) if bucket["n"] else None,
    } for i, bucket in enumerate(groups)]


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
            "actual_home": actual_home,
            "correct": correct if chosen else None,
            "p_home_experimental": p_home,
            "brier": round((p_home - float(actual_home)) ** 2, 6),
            "home_only_correct": actual_home,
            "model_margin": signal.get("margin_experimental"),
            "away_games": signal["away_games"], "home_games": signal["home_games"],
            "model": VERSION,
        })
    candidates = [row for row in evaluated if row["selected"]]
    n, k = len(evaluated), len(candidates)
    wins = sum(row["correct"] for row in candidates)
    coverage = k / n if n else None
    accuracy = wins / k if k else None
    brier = sum(row["brier"] for row in evaluated) / n if n else None
    home_accuracy = sum(int(row["home_only_correct"]) for row in evaluated) / n if n else None
    # A constant 50/50 forecast scores Brier=.25 on binary non-tie events.
    enough = n >= minimum_evaluated and k >= minimum_candidates
    league_rows = {}
    for sport in ("NBA", "NFL", "NHL"):
        sample = [x for x in evaluated if x["sport"] == sport]
        picks = [x for x in sample if x["selected"]]
        if sample:
            league_rows[sport] = {
                "evaluated": len(sample),
                "candidates": len(picks),
                "correct": sum(row["correct"] for row in picks),
                "observed_accuracy": (round(sum(row["correct"] for row in picks)/len(picks), 5)
                                      if picks else None),
                "home_baseline_accuracy": round(
                    sum(int(x["actual_home"]) for x in sample)/len(sample), 5
                ),
                "brier": round(sum(x["brier"] for x in sample)/len(sample), 6),
            }

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
        "candidate_accuracy_wilson_95": wilson_interval(wins, k),
        "home_only_accuracy_evaluated": round(home_accuracy, 5) if home_accuracy is not None else None,
        "candidate_coverage": round(coverage, 5) if coverage is not None else None,
        "brier_all_evaluated": round(brier, 6) if brier is not None else None,
        "brier_50_50_reference": 0.25,
        "calibration_bins": calibration_bins(evaluated),
        "leagues": league_rows,
        "minimum_evaluated": minimum_evaluated,
        "minimum_candidates": minimum_candidates,
        "model_calibrated": False,
        "model_validated": False,
        "stake_recommended": False,
        "notes": ("Sin lookahead: cada corte ocurre antes de la fecha del encuentro. "
                  "El intervalo de Wilson y los promedios NO validan rentabilidad. "
                  "No hay odds históricas sincronizadas ni ROI calculado."),
        "details": evaluated,
    }
