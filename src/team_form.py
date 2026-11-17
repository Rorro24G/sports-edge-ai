"""Formas recientes de equipos NFL/NBA/NHL desde resultados oficiales ESPN.

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
    if sport in ("NBA", "NHL"):
        return day.year + 1 if day.month >= 7 else day.year
    if sport == "NFL":
        return day.year if day.month >= 7 else day.year - 1
    raise ValueError("Solo NBA, NFL o NHL")


def schedule_url(sport: str, team_id: str, day: date) -> str:
    if sport not in ("NBA", "NFL", "NHL") or not re.fullmatch(r"\d{1,8}", str(team_id)):
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
    if sport not in ("NFL", "NBA", "NHL"):
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


def scenario_from_history(sport: str, away_games: list[dict], home_games: list[dict],
                          *, before: date, total_line: float) -> dict:
    """Model a score distribution from prior verified ESPN history.

    Unlike a plain season mean, this uses recency, the opposing defense,
    game-to-game variability, and actual home/away splits when supported.
    Locality and recovery adjustments are explicit hypotheses, NOT learned.
    """
    from math import sqrt

    if sport not in ("NFL", "NBA"):
        raise ValueError("La simulación real admite NBA y NFL")
    if isinstance(total_line, bool) or not isinstance(total_line, (float, int)) or not isfinite(total_line):
        raise ValueError("Línea de puntos no válida")
    if not 0 <= total_line <= 400:
        raise ValueError("Línea de puntos fuera de rango")
    def clean(games):
        result = []
        used = set()
        for row in games:
            if not isinstance(row, dict):
                continue
            try:
                stamp = date.fromisoformat(str(row["date"]))
                pf, pa = float(row["points_for"]), float(row["points_against"])
                event_id = str(row["event_id"])
            except (ValueError, TypeError, KeyError):
                continue
            if (stamp >= before or event_id in used or not event_id
                    or not (isfinite(pf) and isfinite(pa))
                    or min(pf, pa) < 0 or max(pf, pa) > 300):
                continue
            used.add(event_id)
            result.append((stamp, row))
        result.sort(key=lambda x: (x[0], str(x[1]["event_id"])), reverse=True)
        return [row for _, row in result[:12]]
    away = clean(away_games)
    home = clean(home_games)
    if len(away) < 6 or len(home) < 6:
        raise ValueError("Se requieren al menos seis resultados ESPN anteriores por equipo")

    def weight_avg(values):
        weights = [0.88 ** i for i in range(len(values))]
        return sum(w * x for w, x in zip(weights, values)) / sum(weights)

    def averages(games):
        scored = [float(x["points_for"]) for x in games]
        allowed = [float(x["points_against"]) for x in games]
        return weight_avg(scored), weight_avg(allowed), stdev(scored), stdev(allowed)
    af, aa, asd, aad = averages(away)
    hf, ha, hsd, had = averages(home)
    means = [
        (af + ha) / 2,
        (hf + aa) / 2,
    ]
    notes = ["Ataque propio vs defensa rival (ponderación reciente, máximo 12 juegos)"]
    away_venue = [r for r in away if r.get("home") is False]
    home_venue = [r for r in home if r.get("home") is True]
    if len(away_venue) >= 3 and len(home_venue) >= 3:
        # Small venue split adjustment: each venue sample is noisy and may
        # share games with the unconditional estimate.
        venue_away = weight_avg([float(r["points_for"]) for r in away_venue])
        venue_home = weight_avg([float(r["points_for"]) for r in home_venue])
        adjustment_cap = 2.0 if sport == "NBA" else 1.0
        means[0] += max(-adjustment_cap, min(adjustment_cap, (venue_away - af) * .25))
        means[1] += max(-adjustment_cap, min(adjustment_cap, (venue_home - hf) * .25))
        notes.append("Ajuste pequeño de localía con 3+ partidos reales por condición")
    else:
        notes.append("Sin ajuste de localía: muestra en sede insuficiente")

    # Hypothesis: fatigue matters only when recovery time is imbalanced.
    # The size is bounded and intentionally modest; no live injury guesses.
    rest_away = max(0, (before - date.fromisoformat(away[0]["date"])).days - 1)
    rest_home = max(0, (before - date.fromisoformat(home[0]["date"])).days - 1)
    if abs(rest_away - rest_home) >= 2:
        rest_cap = .8 if sport == "NBA" else .6
        rest_bias = rest_cap if rest_home > rest_away else -rest_cap
        means[1] += rest_bias
        notes.append("Ajuste exploratorio de descanso desigual (no calibrado)")

    # Model variability is drawn from both team's own scoring and opposing
    # defensive allowance, with a floor guarding against tiny samples.
    sd_floor = 7.0 if sport == "NBA" else 4.5
    away_sd = max(sd_floor, sqrt(.5 * (asd**2 + had**2)))
    home_sd = max(sd_floor, sqrt(.5 * (hsd**2 + aad**2)))
    return {
        "sport": sport,
        "away_mean": round(max(0, means[0]), 3),
        "home_mean": round(max(0, means[1]), 3),
        "away_sd": round(away_sd, 3),
        "home_sd": round(home_sd, 3),
        "score_correlation": 0.0,  # no matched pair correlation estimated
        "total_line": float(total_line),
        "simulations": 10_000,
        "seed": 42,
        "away_scored": tuple(float(r["points_for"]) for r in away),
        "away_allowed": tuple(float(r["points_against"]) for r in away),
        "home_scored": tuple(float(r["points_for"]) for r in home),
        "home_allowed": tuple(float(r["points_against"]) for r in home),
        "away_count": len(away),
        "home_count": len(home),
        "rest_away": rest_away,
        "rest_home": rest_home,
        "status": "HISTORICO_ESPN_PREPARTIDO_NO_CALIBRADO",
        "method": ". ".join(notes) + ". Se remuestrean marcadores ESPN anteriores y "
                  "se agrega variación residual; correlación asumida cero, no medida.",
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
