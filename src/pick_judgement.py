"""Independent ESPN-only evidence jury for Sports Edge AI.

No Covers odds, consensus, lines, expert picks, or projected scores participate.
This is a conservative and explainable RESEARCH heuristic, not fitted/calibrated.
The jury asks if full-season form, short-term form, trimmed results and
venue-conditioned evidence tell a consistent story before suggesting a side.
"""
from __future__ import annotations

from datetime import date
from math import erf, sqrt
from statistics import stdev


def _weighted(values: list[float]) -> float:
    weights = [0.86 ** i for i in range(len(values))]
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def _projection(away: list[dict], home: list[dict], bonus: float) -> tuple[float, float]:
    attack_away = _weighted([r["points_for"] for r in away])
    defend_away = _weighted([r["points_against"] for r in away])
    attack_home = _weighted([r["points_for"] for r in home])
    defend_home = _weighted([r["points_against"] for r in home])
    return (0.5 * (attack_away + defend_home),
            0.5 * (attack_home + defend_away) + bonus)


def _margin(away: list[dict], home: list[dict], bonus: float) -> float:
    points_away, points_home = _projection(away, home, bonus)
    return points_home - points_away


def _trimmed(games: list[dict]) -> list[dict]:
    """Drop one unusually good and one unusually bad margin; keep date order."""
    if len(games) < 7:
        return list(games)
    ordered = sorted(
        range(len(games)),
        key=lambda i: (games[i]["points_for"] - games[i]["points_against"], i),
    )
    remove = {ordered[0], ordered[-1]}
    return [row for i, row in enumerate(games) if i not in remove]


def _venue_view(away: list[dict], home: list[dict], bonus: float) -> float | None:
    # An explicitly recorded venue is required; unknown flags are not
    # interpreted as away/home. Three games per side is the minimum.
    relevant_away = [r for r in away if r.get("home") is False]
    relevant_home = [r for r in home if r.get("home") is True]
    if len(relevant_away) < 3 or len(relevant_home) < 3:
        return None
    return _margin(relevant_away, relevant_home, bonus)


def _rest(games: list[dict], target: date) -> int:
    # Completed games are strictly prior to the target date.
    return max(0, (target - date.fromisoformat(games[0]["date"])).days - 1)


def judge(away: list[dict], home: list[dict], *, sport: str, config: dict,
          target: date) -> dict:
    """A model verdict from multiple independently computed ESPN signals.

    Directional confidence is NOT a calibrated probability. For pricing,
    leave Covers out of all decision and reliability logic.
    """
    bonus = config["home_bonus"]
    away_pts, home_pts = _projection(away, home, bonus)
    margin = home_pts - away_pts
    recent_margin = _margin(away[:5], home[:5], bonus)
    trimmed_margin = _margin(_trimmed(away), _trimmed(home), bonus)
    venue_margin = _venue_view(away, home, bonus)

    sd_away = stdev([r["points_for"] - r["points_against"] for r in away])
    sd_home = stdev([r["points_for"] - r["points_against"] for r in home])
    uncertainty = max(config["floor_sd"], sqrt((sd_away ** 2 + sd_home ** 2) / 2))
    p_home_raw = 0.5 * (1 + erf(margin / (uncertainty * sqrt(2))))
    # Deliberately shrink extremes toward 50/50 when sample sizes are small.
    evidence_weight = min(0.90, 0.55 + 0.035 * min(len(away), len(home)))
    p_home = min(0.95, max(0.05, 0.5 + (p_home_raw - 0.5) * evidence_weight))
    side = "local" if margin > 0 else "visitante"
    side_sign = 1 if margin > 0 else -1
    p_selected = p_home if side == "local" else 1 - p_home

    # Drop either edge of each history as an adversarial sensitivity test.
    leave_one_out = [
        _margin(away[1:], home, bonus),
        _margin(away[:-1], home, bonus),
        _margin(away, home[1:], bonus),
        _margin(away, home[:-1], bonus),
    ]
    stability = sum(1 for m in leave_one_out if side_sign * m > 0) / len(leave_one_out)
    checks = {
        "Historial completo": round(margin, 2),
        "Últimos 5": round(recent_margin, 2),
        "Sin marcadores extremos": round(trimmed_margin, 2),
    }
    if venue_margin is not None:
        checks["Según localía real"] = round(venue_margin, 2)

    contradictions = []
    # Each independently computed view can veto a weak conclusion.
    for label, value in checks.items():
        if side_sign * value <= 0:
            contradictions.append(label + " favorece al otro equipo")
    if stability < 0.75:
        contradictions.append("La selección cambia al excluir un solo resultado")

    # Fragile short-turnaround teams are flagged, not given arbitrary points.
    rest_away, rest_home = _rest(away, target), _rest(home, target)
    if sport in {"NBA", "NHL"} and min(rest_away, rest_home) == 0:
        if side == "visitante" and rest_away == 0 and rest_home >= 2:
            contradictions.append("Visitante sin día de descanso frente a rival descansado")
        if side == "local" and rest_home == 0 and rest_away >= 2:
            contradictions.append("Local sin día de descanso frente a rival descansado")

    max_age = 28 if sport == "NFL" else 14
    if max(rest_away, rest_home) > max_age:
        contradictions.append("Resultados demasiado antiguos para emitir una señal")

    # Scenario stress: even after removing the assumed home advantage, the
    # selected side should not reverse. This is not a learned home coefficient.
    neutral_margin = _margin(away, home, 0.0)
    if side_sign * neutral_margin <= 0:
        contradictions.append("La elección depende únicamente de la localía asumida")

    enough_margin = abs(margin) >= {"NBA": 3.0, "NFL": 2.2, "NHL": 0.40}[sport]
    if not enough_margin:
        contradictions.append("Diferencia de marcador demasiado pequeña")
    if p_selected < 0.58:
        contradictions.append("Señal exploratoria débil frente a un 50/50")
    if uncertainty > config["floor_sd"] * 2.6 and abs(margin) < uncertainty * 0.55:
        contradictions.append("Resultados muy variables para esta diferencia")

    candidate = not contradictions
    summary = (
        f"{len(away)} y {len(home)} partidos anteriores ESPN; "
        f"historial completo, últimos 5, extremos y localía contrastados. "
        + ("Señales consistentes." if candidate
           else "Juicio descartado: " + "; ".join(contradictions) + ".")
    )
    return {
        "status": "CANDIDATO_EXPERIMENTAL" if candidate else "PASAR",
        "side": side,
        "probability_experimental": round(p_selected, 4),
        "probability_home_experimental": round(p_home, 4),
        "predicted_home": round(home_pts, 1),
        "predicted_away": round(away_pts, 1),
        "margin_experimental": round(abs(margin), 1),
        "status_reason": summary,
        "evidence": checks,
        "contradictions": contradictions,
        "stability": stability,
        "uncertainty_points": round(uncertainty, 2),
        "rest_days": {"visitante": rest_away, "local": rest_home},
        "evidence_weight": round(evidence_weight, 3),
        "calibration_status": "NO_CALIBRADO",
        "market_input_used": False,
        "model_validated": False,
    }
