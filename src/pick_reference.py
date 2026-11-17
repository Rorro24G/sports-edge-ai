"""Evidencia de pronósticos públicos; no es modelo propio ni cuota.

Las proyecciones numéricas de Covers permiten identificar el resultado que
favorece su marcador, pero no prueban una probabilidad de ganar ni un valor EV.
"""
from __future__ import annotations
from datetime import date, datetime
from math import isfinite
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("America/Mexico_City")
TEAM_MEXICO_URL = "https://www.teammexico.mx/"
SCOUT_PICKS_URL = "https://scoutpicks.app/dashboard/"


def _score(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if not isfinite(number) or number < 0 or number > 250:
        return None
    return number


def covers_projection(game: dict, *, now: datetime | None = None) -> dict | None:
    """Returns what Covers' predicted score favors, with clear provenance.

    This NEVER claims that Covers editorially recommended a moneyline bet.
    A past or already started game is labelled historical, not actionable.
    """
    parts = str(game.get("partido") or "").split(" @ ", 1)
    if len(parts) != 2 or game.get("liga") not in ("NBA", "NFL", "NHL"):
        return None
    away, home = parts
    left = _score(game.get("proyeccion_visitante"))
    right = _score(game.get("proyeccion_local"))
    if left is None or right is None or left == right:
        return None
    try:
        starts = datetime.fromisoformat(
            str(game["fecha_cdmx"]) + "T" + str(game["hora_cdmx"])
        ).replace(tzinfo=LOCAL)
    except (KeyError, ValueError, TypeError):
        return None
    clock = now or datetime.now(LOCAL)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=LOCAL)
    is_future = starts > clock.astimezone(LOCAL)
    winner_is_away = left > right
    side = "visitante" if winner_is_away else "local"
    projected_team = away if winner_is_away else home
    return {
        "liga": game["liga"],
        "partido": game["partido"],
        "fecha_cdmx": game["fecha_cdmx"],
        "hora_cdmx": game["hora_cdmx"],
        "equipo_proyectado": projected_team,
        "lado_proyectado": side,
        "marcador_proyectado": f"{left:g} - {right:g}",
        "margen_proyectado": round(abs(left - right), 2),
        "total_proyectado": round(left + right, 2),
        "tipo": "REFERENCIA_DE_PROYECCION_EXTERNA",
        "fuente": game.get("fuente") or "",
        "vigente_para_analisis_prepartido": is_future,
        "probabilidad_propia": None,
        "ev_propio": None,
        "pick_validado": False,
        "stake_recomendado": None,
        "motivo_bloqueo": (
            "Sin modelo propio calibrado, momio contrastado y ventaja validada"
        ),
    }


def visible_projections(events: list[dict], *, now: datetime | None = None) -> list[dict]:
    """Only future external projected winners are visible as today's references."""
    rows = []
    for game in events:
        candidate = covers_projection(game, now=now)
        if candidate is not None and candidate["vigente_para_analisis_prepartido"]:
            rows.append(candidate)
    return sorted(rows, key=lambda row: (row["fecha_cdmx"], row["hora_cdmx"], row["liga"]))
