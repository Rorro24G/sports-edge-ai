"""Formas recientes de equipos NFL/NBA desde resultados oficiales ESPN.

Los datos solamente incluyen partidos COMPLETADOS antes de la fecha del
encuentro a analizar. Las medias son descripciones, NO un modelo calibrado.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from statistics import mean, stdev
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import json
import re

from .live_board import SPORT_PATH

LOCAL = ZoneInfo("America/Mexico_City")


class TeamFormError(RuntimeError):
    pass


def season_year(sport: str, day: date) -> int:
    if sport == "NBA":
        return day.year + 1 if day.month >= 7 else day.year
    if sport == "NFL":
        return day.year if day.month >= 7 else day.year - 1
    raise ValueError("Solo NBA o NFL")


def schedule_url(sport: str, team_id: str, day: date) -> str:
    if sport not in ("NBA", "NFL") or not re.fullmatch(r"\d{1,8}", str(team_id)):
        raise ValueError("Deporte o equipo no válido")
    group, league = SPORT_PATH[sport]
    return (f"https://site.api.espn.com/apis/site/v2/sports/{group}/{league}"
            f"/teams/{team_id}/schedule?" +
            urlencode({"season": season_year(sport, day), "seasontype": 2}))


def _score(raw: object) -> float | None:
    if isinstance(raw, dict):
        raw = raw.get("value", raw.get("displayValue"))
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(value) or not 0 <= value <= 300:
        return None
    return value


def completed_team_games(payload: dict, sport: str, team_id: str,
                         before: date) -> list[dict]:
    """ESPN schedule events to verified per-team chronological results."""
    if sport not in ("NFL", "NBA"):
        raise ValueError("Liga sin historial conectado")
    events = payload.get("events") or []
    if not isinstance(events, list):
        return []
    found = {}
    for event in events[:150]:
        if not isinstance(event, dict):
            continue
        try:
            kickoff = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
            if kickoff.tzinfo is None:
                continue
            day = kickoff.astimezone(LOCAL).date()
            if day >= before:
                continue
            competitions = event["competitions"]
            competition = competitions[0]
            # ESPN team schedules put FINAL on competitions[0].status,
            # not on event.status (unlike ESPN scoreboard).
            status = event.get("status") or competition.get("status") or {}
            type_status = status.get("type") if isinstance(status, dict) else {}
            if not isinstance(type_status, dict):
                continue
            if not (type_status.get("completed") is True or
                    str(type_status.get("state", "")).lower() == "post"):
                continue
            competitors = competition["competitors"]
            if len(competitors) != 2:
                continue
            team = next((x for x in competitors if
                         str((x.get("team") or {}).get("id") or "") == str(team_id)), None)
            opponent = next((x for x in competitors if x is not team), None)
            if team is None or opponent is None:
                continue
            own, rival = _score(team.get("score")), _score(opponent.get("score"))
            if own is None or rival is None:
                continue
            event_id = str(event.get("id") or "")
            if not event_id.isdecimal():
                continue
            found[event_id] = {
                "event_id": event_id, "date": day.isoformat(),
                "points_for": own, "points_against": rival,
                "home": team.get("homeAway") == "home",
                "opponent": str((opponent.get("team") or {}).get("displayName") or
                                (opponent.get("team") or {}).get("abbreviation") or ""),
                "result": "W" if own > rival else "L" if own < rival else "T",
            }
        except (KeyError, TypeError, IndexError, ValueError, StopIteration):
            continue
    return sorted(found.values(), key=lambda row: (row["date"], row["event_id"]),
                  reverse=True)


def recent_team_form(games: list[dict], *, last: int = 10,
                     minimum: int = 5) -> dict | None:
    if not isinstance(last, int) or not 2 <= last <= 30:
        raise ValueError("Número de partidos inválido")
    if not 2 <= minimum <= last:
        raise ValueError("Muestra mínima inválida")
    data = games[:last]
    if len(data) < minimum:
        return None
    scored = [g["points_for"] for g in data]
    conceded = [g["points_against"] for g in data]
    return {
        "partidos": len(data),
        "puntos_anotados_media": round(mean(scored), 2),
        "puntos_recibidos_media": round(mean(conceded), 2),
        "desviacion_anotados": round(stdev(scored), 2),
        "desviacion_recibidos": round(stdev(conceded), 2),
        "racha": "".join(row["result"] for row in data[:5]),
        "partidos_reales": data,
        "tipo": "RESULTADOS_HISTORICOS_ESPN_NO_PREDICCION",
    }


def scenario_from_forms(sport: str, away: dict, home: dict,
                        *, total_line: float) -> dict:
    """Transparent noncalibrated what-if parameters, never a betting pick."""
    if sport not in ("NBA", "NFL"):
        raise ValueError("Liga de escenario no admitida")
    if not (isinstance(total_line, (int, float)) and
            not isinstance(total_line, bool) and isfinite(total_line) and
            total_line >= 0):
        raise ValueError("Línea total inválida")
    for sample in (away, home):
        if not sample or sample.get("partidos", 0) < 5:
            raise ValueError("Se necesitan cinco resultados previos por equipo")
    return {
        "sport": sport,
        "away_mean": round((away["puntos_anotados_media"]
                            + home["puntos_recibidos_media"]) / 2, 2),
        "home_mean": round((home["puntos_anotados_media"]
                            + away["puntos_recibidos_media"]) / 2, 2),
        "away_sd": max(1.0, away["desviacion_anotados"]),
        "home_sd": max(1.0, home["desviacion_anotados"]),
        "score_correlation": 0.0,
        "total_line": total_line,
        "simulations": 10_000,
        "seed": 42,
        "status": "ESCENARIO_DE_DESCRIPCION_HISTORICA_NO_VALIDADO",
        "method": "Media de ataque propio y puntos permitidos rivales de los "
                  "últimos partidos ESPN. Correlación 0 como hipótesis NO medida, "
                  "no implica independencia real ni validación predictiva.",
    }


def fetch_team_schedule(sport: str, team_id: str, day: date) -> dict:
    url = schedule_url(sport, team_id, day)
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "SportsEdgeAI-personal/1.0",
    })
    try:
        with urlopen(request, timeout=13) as response:
            content = response.read(2_500_001)
        if len(content) > 2_500_000:
            raise TeamFormError("ESPN devolvió demasiados datos")
        payload = json.loads(content)
    except HTTPError as exc:
        raise TeamFormError("ESPN respondió HTTP " + str(exc.code)) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise TeamFormError("ESPN no entregó calendario histórico verificable") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise TeamFormError("Respuesta de ESPN sin eventos válidos")
    return {
        "sport": sport, "team_id": str(team_id),
        "source_url": url, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "games": completed_team_games(payload, sport, str(team_id), day),
    }
