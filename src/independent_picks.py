"""Sports Edge AI independent pregame baseline, fed ONLY by ESPN team results.

Covers is an optional price source. Its projected scores, expert picks, consensus
and moneylines never enter the model or determine the selected team.

This is a transparent experimental model, not a trained/calibrated betting edge.
All selections are research hypotheses, with no stake recommendation.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from math import erf, isfinite, sqrt
from statistics import mean, stdev
from zoneinfo import ZoneInfo

from .market_summary import implied_percent
from .pick_context import match_espn_event
from .team_form import TeamFormError

MX = ZoneInfo("America/Mexico_City")
VERSION = "SEAI-FORMA-0.1"
# Home edge and variance floors are transparent *hypotheses*; not fitted.
SPEC = {
    "NBA": {"min_games": 7, "home_bonus": 2.0, "floor_sd": 13.0, "window": 10},
    "NFL": {"min_games": 5, "home_bonus": 1.5, "floor_sd": 10.0, "window": 8},
    "NHL": {"min_games": 7, "home_bonus": 0.20, "floor_sd": 2.7, "window": 10},
}
LIVE = {"PRE", "SCHEDULED", "STATUS_SCHEDULED", "STATUS_PRE"}


def _clock(now: datetime | None) -> datetime:
    stamp = now or datetime.now(MX)
    return stamp.replace(tzinfo=MX) if stamp.tzinfo is None else stamp.astimezone(MX)


def _pregame(game: dict, target: date, now: datetime | None) -> bool:
    if str(game.get("status", "")).upper() not in LIVE:
        return False
    if not game.get("local_time"):
        return False
    try:
        kickoff = datetime.fromisoformat(target.isoformat() + "T" + game["local_time"]).replace(tzinfo=MX)
    except (TypeError, ValueError):
        return False
    return kickoff > _clock(now)


def _history(raw: dict | None, target: date, window: int) -> list[dict]:
    """Reject even same-day games and malformed outcomes; never use future results."""
    games = (raw or {}).get("games") or []
    if not isinstance(games, list):
        return []
    good = []
    seen = set()
    for row in games:
        if not isinstance(row, dict):
            continue
        try:
            stamp = date.fromisoformat(str(row["date"]))
            pf, pa = float(row["points_for"]), float(row["points_against"])
            key = str(row["event_id"])
        except (KeyError, ValueError, TypeError):
            continue
        if (stamp >= target or not key or key in seen
                or not isfinite(pf) or not isfinite(pa)
                or pf < 0 or pa < 0 or pf > 300 or pa > 300):
            continue
        seen.add(key)
        good.append((stamp, row))
    good.sort(key=lambda pair: (pair[0], str(pair[1]["event_id"])), reverse=True)
    return [row for _, row in good[:window]]


def _weighted(values: list[float]) -> float:
    weights = [.86 ** i for i in range(len(values))]
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def predict_from_results(sport: str, away: str, home: str,
                         away_data: dict, home_data: dict, target: date) -> dict:
    """Make an independent directional choice with pregame ESPN evidence only."""
    if sport not in SPEC:
        return {"status": "NO_ANALIZABLE", "reason": "Liga sin motor propio"}
    cfg = SPEC[sport]
    away_games = _history(away_data, target, cfg["window"])
    home_games = _history(home_data, target, cfg["window"])
    minimum = cfg["min_games"]
    if len(away_games) < minimum or len(home_games) < minimum:
        return {
            "status": "SIN_DATOS",
            "reason": f"Se requieren al menos {minimum} resultados previos por equipo",
            "away_games": len(away_games), "home_games": len(home_games),
            "version": VERSION,
        }
    af = _weighted([r["points_for"] for r in away_games])
    aa = _weighted([r["points_against"] for r in away_games])
    hf = _weighted([r["points_for"] for r in home_games])
    ha = _weighted([r["points_against"] for r in home_games])
    # Both offenses are contrasted against the opposing defenses.
    away_pts = .5 * (af + ha)
    home_pts = .5 * (hf + aa) + cfg["home_bonus"]
    # Spread of game margins is wider than a score's isolated variance;
    # use observed margins with an explicit sport-specific uncertainty floor.
    a_margin_sd = stdev([r["points_for"] - r["points_against"] for r in away_games])
    h_margin_sd = stdev([r["points_for"] - r["points_against"] for r in home_games])
    sd = max(cfg["floor_sd"], sqrt((a_margin_sd ** 2 + h_margin_sd ** 2) / 2))
    p_home = .5 * (1 + erf((home_pts - away_pts) / (sd * sqrt(2))))
    p_home = min(.99, max(.01, p_home))
    side = "local" if p_home > .5 else "visitante"
    p_selected = p_home if side == "local" else 1 - p_home
    # Minimum separation avoids manufacturing picks for near coin-flips.
    candidate = p_selected >= .57
    return {
        "status": "CANDIDATO_EXPERIMENTAL" if candidate else "PASAR",
        "team": home if side == "local" else away,
        "side": side,
        "probability_experimental": round(p_selected, 4),
        "probability_home_experimental": round(p_home, 4),
        "predicted_home": round(home_pts, 1),
        "predicted_away": round(away_pts, 1),
        "margin_experimental": round(abs(home_pts - away_pts), 1),
        "away_games": len(away_games),
        "home_games": len(home_games),
        "reason": ("Señal estadística propia con ventaja direccional"
                   if candidate else "Partido demasiado equilibrado para seleccionar"),
        "version": VERSION,
        "model_validated": False,
        "calibrated": False,
        "stake": 0,
        "source": "ESPN team schedules",
    }


def evaluate_game(game: dict, target: date, *,
                  team_fetch, now: datetime | None = None) -> dict:
    """Generate a self-owned signal for one exact ESPN event."""
    base = {
        "event_id": str(game.get("event_id") or ""),
        "sport": game.get("sport", ""), "away": game.get("away", ""),
        "home": game.get("home", ""),
        "time": game.get("local_time", ""),
        "espn_url": game.get("source_url", ""),
        "version": VERSION,
    }
    if base["sport"] not in SPEC:
        return {**base, "status": "NO_ANALIZABLE", "reason": "Liga no soportada"}
    if not _pregame(game, target, now):
        return {**base, "status": "NO_ANALIZABLE",
                "reason": "El encuentro ya empezó, terminó o no tiene hora válida"}
    if not (str(game.get("away_team_id", "")).isdigit()
            and str(game.get("home_team_id", "")).isdigit()):
        return {**base, "status": "SIN_DATOS", "reason": "ESPN no entregó IDs de ambos equipos"}
    try:
        away_data = team_fetch(base["sport"], str(game["away_team_id"]), target)
        home_data = team_fetch(base["sport"], str(game["home_team_id"]), target)
    except (TeamFormError, ValueError, OSError, KeyError, TypeError):
        return {**base, "status": "SIN_DATOS",
                "reason": "No se pudo cargar el historial ESPN de ambos equipos"}
    return {
        **base,
        **predict_from_results(base["sport"], base["away"], base["home"],
                               away_data, home_data, target),
        "espn_history_urls": [away_data.get("source_url", ""),
                              home_data.get("source_url", "")],
    }


def add_covers_price(result: dict, original_game: dict,
                     covers_events: list[dict], target: date) -> dict:
    """Attach optional market moneyline AFTER the independent selection."""
    merged = dict(result)
    merged.update({"market_price": None, "market_source": None,
                   "market_break_even_percent": None})
    if result.get("status") not in {"CANDIDATO_EXPERIMENTAL", "PASAR"}:
        return merged
    matches = []
    for event in covers_events:
        if (event.get("liga") == original_game.get("sport")
                and event.get("fecha_cdmx") == target.isoformat()
                and event.get("hora_cdmx") == original_game.get("local_time")
                and match_espn_event(event, [original_game]) is not None):
            matches.append(event)
    if len(matches) != 1:
        return merged
    matched = matches[0]
    field = "momio_local" if result.get("side") == "local" else "momio_visitante"
    price = matched.get(field)
    implied = implied_percent(price)
    if implied is not None:
        merged.update({
            "market_price": str(price),
            "market_source": matched.get("fuente"),
            "market_break_even_percent": implied,
        })
    return merged


def build_slate(boards: dict[str, list[dict]], target: date, *,
                team_fetch, covers_events: list[dict] | None = None,
                now: datetime | None = None,
                per_league: int = 5) -> dict:
    """Evaluate future ESPN games, not the favorites named on Covers."""
    if not 1 <= per_league <= 8:
        raise ValueError("per_league fuera de rango")
    fixtures = []
    total = 0
    for sport in SPEC:
        current = [game for game in boards.get(sport, [])
                   if game.get("sport") == sport and _pregame(game, target, now)]
        current.sort(key=lambda g: (g.get("local_time", ""), g.get("event_id", "")))
        total += len(current)
        fixtures.extend(current[:per_league])
    if not fixtures:
        return {"picks": [], "evaluated": [], "eligible_games": 0,
                "model": VERSION, "status": "SIN_PARTIDOS_PREVIOS"}
    # Team histories are read-only. Parallel fetch reduces cold-start latency.
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(evaluate_game, game, target,
                               team_fetch=team_fetch, now=now): game
                   for game in fixtures}
        out = []
        for future in as_completed(futures):
            game = futures[future]
            try:
                result = future.result()
            except Exception:
                # Missing external data must never become a fabricated pick.
                result = {"event_id": game.get("event_id", ""), "sport": game["sport"],
                          "away": game.get("away", ""), "home": game.get("home", ""),
                          "status": "SIN_DATOS", "reason": "Error al leer datos ESPN"}
            out.append(add_covers_price(result, game, covers_events or [], target))
    out.sort(key=lambda r: (r.get("sport", ""), r.get("time", ""), r.get("event_id", "")))
    candidates = [r for r in out if r.get("status") == "CANDIDATO_EXPERIMENTAL"]
    candidates.sort(key=lambda r: r.get("probability_experimental", 0), reverse=True)
    return {"picks": candidates, "evaluated": out,
            "eligible_games": total, "model": VERSION,
            "status": "EXPERIMENTAL_SIN_BACKTEST_VALIDADO"}
