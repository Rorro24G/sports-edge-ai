"""Opponent-strength challenger for the independent Sports Edge AI model.

The existing live SEAI-JUICIO-0.2 verdict remains unchanged. This challenger
tries to REFUTE its selections using strength of the opponents faced BEFORE
each historic game. Never uses Covers, market odds, current rankings or any
result observed after the fixture under consideration.

Do NOT call these experimental counters calibrated probabilities.
"""
from __future__ import annotations

from datetime import date
from math import isfinite

from .independent_picks import VERSION, predict_from_results


SPORT_CAPS = {"NBA": 2.4, "NFL": 1.6, "NHL": .38}
MIN_RECENT = 4


def _prior_rows(data: dict, before: date, *, last: int = 10) -> list[dict]:
    rows = []
    seen = set()
    for row in (data or {}).get("games", []):
        try:
            day = date.fromisoformat(str(row["date"]))
            event = str(row["event_id"])
            pf = float(row["points_for"])
            pa = float(row["points_against"])
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
        if (day >= before or not event.isdecimal() or event in seen
                or not isfinite(pf) or not isfinite(pa)
                or min(pf, pa) < 0 or max(pf, pa) > 300):
            continue
        rows.append((day, event, row))
        seen.add(event)
    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [row for _, _, row in rows[:last]]


def _past_strength(data: dict, before: date) -> float | None:
    games = _prior_rows(data, before, last=8)
    if len(games) < 3:
        return None
    weight = [.88 ** i for i in range(len(games))]
    return sum(w * (g["points_for"] - g["points_against"])
               for w, g in zip(weight, games)) / sum(weight)


def event_team_index(histories: dict[tuple[str, str], dict], sport: str
                     ) -> dict[str, list[tuple[str, dict]]]:
    """Pair ESPN team schedules by same completed event ID; never fuzzy-match names."""
    result: dict[str, list[tuple[str, dict]]] = {}
    for (league, team_id), data in histories.items():
        if league != sport:
            continue
        for row in (data or {}).get("games", []):
            if not isinstance(row, dict):
                continue
            eid = str(row.get("event_id", ""))
            if eid.isdecimal():
                result.setdefault(eid, []).append((team_id, row))
    return result


def team_opponent_quality(sport: str, team_id: str, target: date,
                          histories: dict[tuple[str, str], dict],
                          index: dict[str, list[tuple[str, dict]]]
                          ) -> dict:
    """Difficulty is opponent's point margin known *before* the actual meeting."""
    own = _prior_rows(histories.get((sport, team_id), {}), target)
    evidence = []
    for row in own:
        candidates = [
            (rival_id, rival_row)
            for rival_id, rival_row in index.get(str(row["event_id"]), [])
            if rival_id != team_id
            and rival_row.get("date") == row["date"]
        ]
        if len(candidates) != 1:
            continue
        opponent_id, _ = candidates[0]
        # The opponent's pregame form must be computed BEFORE THAT game,
        # not as of the future target game being predicted.
        before_game = date.fromisoformat(row["date"])
        strength = _past_strength(histories.get((sport, opponent_id), {}),
                                  before_game)
        if strength is not None:
            evidence.append((row, strength))
    if len(evidence) < MIN_RECENT:
        return {"available": False, "reason": "Historial previo de rivales insuficiente",
                "matched_opponents": len(evidence), "games": len(own)}
    weight = [.86 ** i for i in range(len(evidence))]
    quality = sum(w * strength for w, (_, strength) in zip(weight, evidence)) / sum(weight)
    return {
        "available": True,
        "difficulty": round(quality, 4),
        "matched_opponents": len(evidence),
        "games": len(own),
        "as_of": target.isoformat(),
        "source": "ESPN prior completed games of historical opponents",
    }


def challenge_pick(sport: str, away_id: str, home_id: str, target: date,
                   baseline: dict, histories: dict[tuple[str, str], dict],
                   *, index: dict[str, list[tuple[str, dict]]] | None = None) -> dict:
    """Veto a fragile baseline winner; NEVER manufacture new picks."""
    if baseline.get("status") != "CANDIDATO_EXPERIMENTAL":
        return {"verdict": "NO_BASELINE_PICK", "veto": False}
    if sport not in SPORT_CAPS:
        return {"verdict": "UNSUPPORTED", "veto": False}
    idx = index if index is not None else event_team_index(histories, sport)
    away = team_opponent_quality(sport, away_id, target, histories, idx)
    home = team_opponent_quality(sport, home_id, target, histories, idx)
    if not away["available"] or not home["available"]:
        return {
            "verdict": "INSUFFICIENT_OPPONENT_HISTORY",
            "veto": False, "assessable": False,
            "away": away, "home": home,
        }
    side = baseline["side"]
    original_home_margin = (
        baseline["margin_experimental"] * (1 if side == "local" else -1)
    )
    difference = home["difficulty"] - away["difficulty"]
    raw_adjustment = difference * .30
    cap = SPORT_CAPS[sport]
    adjustment = max(-cap, min(cap, raw_adjustment))
    adjusted = original_home_margin + adjustment
    original_side_margin = abs(original_home_margin)
    revised_side_margin = adjusted * (1 if side == "local" else -1)
    # If the diagnosis erases >40% of the asserted margin, the original
    # judgment was too dependent on an unadjusted schedule. Abstain.
    veto = revised_side_margin <= original_side_margin * .60
    return {
        "verdict": "VETO" if veto else "CONSISTENT",
        "veto": veto,
        "assessable": True,
        "baseline_side": side,
        "original_margin": round(original_home_margin, 4),
        "revised_margin": round(adjusted, 4),
        "opponent_quality_adjustment": round(adjustment, 4),
        "away": away,
        "home": home,
        "baseline_version": VERSION,
        "challenger_version": "SEAI-RIVALES-0.3-EXPERIMENTAL",
        "source": "ESPN team schedules, opponent point margin before each meeting",
        "production_enabled": False,
    }


def compare_challenger(fixtures: list[dict],
                       histories: dict[tuple[str, str], dict],
                       *, minimum_evaluated: int = 30) -> dict:
    """Compare baseline vs challenger on IDENTICAL, assessable ESPN candidates."""
    from .pick_walkforward import walkforward

    historical = walkforward(fixtures, histories,
                             minimum_evaluated=minimum_evaluated,
                             minimum_candidates=10)
    fixtures_by_id = {
        (g.get("sport"), str(g.get("event_id"))): g
        for g in fixtures
    }
    selected = [row for row in historical["details"] if row["selected"]]
    indices = {sport: event_team_index(histories, sport)
               for sport in ("NBA", "NFL", "NHL")}
    assessable = []
    kept = []
    vetoed = []
    excluded = []
    for row in selected:
        game = fixtures_by_id.get((row["sport"], row["event_id"]))
        if not game:
            continue
        sport = row["sport"]
        target = date.fromisoformat(row["date"])
        baseline = predict_from_results(
            sport, game["away"], game["home"],
            histories.get((sport, str(game["away_team_id"])), {}),
            histories.get((sport, str(game["home_team_id"])), {}),
            target,
        )
        result = challenge_pick(
            sport, str(game["away_team_id"]), str(game["home_team_id"]),
            target, baseline, histories, index=indices[sport],
        )
        enriched = {
            "event_id": row["event_id"], "date": row["date"],
            "baseline_correct": row["correct"],
            "baseline_probability": row["p_selected_experimental"],
            "opponent_challenge": result,
        }
        if not result.get("assessable"):
            excluded.append(enriched)
            continue
        assessable.append(enriched)
        (vetoed if result["veto"] else kept).append(enriched)
    def accuracy(rows):
        return round(sum(x["baseline_correct"] for x in rows)/len(rows), 5) if rows else None

    n = len(assessable)
    k = len(kept)
    return {
        "model": "SEAI-RIVALES-0.3-EXPERIMENTAL",
        "baseline_version": VERSION,
        "production_enabled": False,
        "comparison": "IDENTICAL_ASSESSABLE_HISTORICAL_PICKS",
        "historical_baseline_candidates": len(selected),
        "assessable_candidates": n,
        "unassessable_candidates": len(excluded),
        "vetoed_candidates": len(vetoed),
        "retained_candidates": k,
        "baseline_accuracy_all_candidates": accuracy([
            {"baseline_correct": x["correct"]} for x in selected
        ]),
        "baseline_accuracy_assessable": accuracy(assessable),
        "challenger_accuracy_retained": accuracy(kept),
        "baseline_accuracy_vetoed": accuracy(vetoed),
        "retained_count_correct": sum(x["baseline_correct"] for x in kept),
        "vetoed_count_correct": sum(x["baseline_correct"] for x in vetoed),
        "data_complete": bool(historical["evaluated_count"]),
        "eligible_for_promotion": False,
        "notes": (
            "No usa cuotas ni picks de Covers. La regla de veto es una hipótesis "
            "no calibrada; sesgo por muestra pequeña. No utilizar en vivo sin "
            "validación prospectiva y comparación de temporadas."
        ),
        "details": {"retained": kept, "vetoed": vetoed,
                    "unassessable": excluded},
    }
