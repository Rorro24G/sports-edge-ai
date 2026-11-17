"""Consulta NBA de puntos, rebotes, asistencias y triples usando ESPN.

ESPN no suministra un precio de apuesta en su gamelog. Un porcentaje histórico
sobre una línea suministrada por el usuario NO es probabilidad predictiva ni EV.
Todos los partidos del estudio ocurrieron ANTES del día de la consulta.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import isfinite
from statistics import mean
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .web_query import normalized

MX = ZoneInfo("America/Mexico_City")
ROSTER_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
GAMELOG_BASE = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes"
STATS = {
    "PTS": (r"\bpuntos?\b", r"\bpoints?\b", r"\bpts\b"),
    "REB": (r"\brebotes?\b", r"\brebounds?\b", r"\breb\b"),
    "AST": (r"\basistencias?\b", r"\bassists?\b", r"\bast\b"),
    "3PM": (r"\btriples?\b", r"\b3pm\b", r"\b3pt\b", r"\b3-pointers?\b"),
}
STAT_LABELS = {
    "PTS": ("PTS",), "REB": ("REB",),
    "AST": ("AST",), "3PM": ("3PM", "3PT", "3P", "3PTM"),
}


class PlayerSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlayerQuestion:
    stat: str
    direction: str | None
    line: float | None


def parse_player_question(text: str) -> PlayerQuestion | None:
    q = normalized(text)
    stat = next((name for name, patterns in STATS.items()
                 if any(re.search(pattern, q) for pattern in patterns)), None)
    if not stat:
        return None
    over = bool(re.search(r"\b(?:over|mas de|supera|superara|por encima)\b", q))
    under = bool(re.search(r"\b(?:under|menos de|por debajo)\b", q))
    if over and under:
        return PlayerQuestion(stat, None, None)
    direction = "over" if over else "under" if under else None
    num = r"(\d{1,3}(?:[.,]\d{1,2})?)"
    expression = r"(?:puntos?|points?|pts|rebotes?|rebounds?|reb|asistencias?|assists?|ast|triples?|3pm|3pt|3-pointers?)"
    patterns = [
        r"\b(?:over|under|mas de|menos de|supera|superara|por encima de|por debajo de)\s+(?:de\s+)?" + num,
        r"\b" + expression + r"\s*(?:de\s*)?" + num,
        r"\b" + num + r"\s+" + expression + r"\b",
    ]
    line = None
    for pattern in patterns:
        found = re.search(pattern, q)
        if found:
            candidate = float(found.group(1).replace(",", "."))
            if isfinite(candidate) and 0 < candidate <= 100.5:
                line = candidate
                break
    return PlayerQuestion(stat, direction, line)


def _request_json(url: str, max_bytes: int = 2_000_000) -> dict:
    request = Request(url, headers={
        "User-Agent": "SportsEdgeAI-personal/1.0",
        "Accept": "application/json",
    })
    try:
        with urlopen(request, timeout=12) as response:
            content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise PlayerSourceError("ESPN devolvió más datos de los permitidos")
        data = json.loads(content)
    except HTTPError as exc:
        raise PlayerSourceError("ESPN respondió HTTP " + str(exc.code)) from None
    except (URLError, OSError, TimeoutError, ValueError):
        raise PlayerSourceError("No se pudo consultar ESPN en este momento") from None
    if not isinstance(data, dict):
        raise PlayerSourceError("Respuesta no válida de ESPN")
    return data


def roster_url(team_id: str) -> str:
    if not re.fullmatch(r"\d{1,8}", str(team_id)):
        raise ValueError("Identificador de equipo no válido")
    return f"{ROSTER_BASE}/{team_id}/roster"


def gamelog_url(athlete_id: str, season: int) -> str:
    if not re.fullmatch(r"\d{1,12}", str(athlete_id)) or not 2000 <= season <= 2100:
        raise ValueError("Identificador de jugador o temporada no válido")
    return f"{GAMELOG_BASE}/{athlete_id}/gamelog?season={season}"


def season_for(day: date) -> int:
    return day.year + 1 if day.month >= 7 else day.year


def parse_roster(payload: dict, team_id: str) -> list[dict]:
    people = payload.get("athletes") or []
    if not isinstance(people, list):
        return []
    result = []
    for group in people[:100]:
        if not isinstance(group, dict):
            continue
        entries = group.get("items")
        if not isinstance(entries, list):
            entries = [group]
        for player in entries[:100]:
            if not isinstance(player, dict):
                continue
            player_id = str(player.get("id") or "")
            name = str(player.get("displayName") or player.get("fullName") or "")
            if re.fullmatch(r"\d{1,12}", player_id) and name:
                injuries = player.get("injuries")
                status = player.get("status")
                result.append({
                    "id": player_id, "name": name, "team_id": str(team_id),
                    "injuries": injuries if isinstance(injuries, list) else [],
                    "status": status.get("name") if isinstance(status, dict) else None,
                })
    return result


def fetch_roster(team_id: str) -> dict:
    url = roster_url(team_id)
    return {"athletes": parse_roster(_request_json(url), str(team_id)),
            "source_url": url,
            "checked_at_utc": datetime.now(timezone.utc).isoformat()}


def resolve_player(query: str, players: list[dict]) -> dict | None:
    """Require a unique full name, or unique surname among candidates."""
    normalized_query = normalized(query)
    unique = {str(p.get("id")): p for p in players if p.get("id") and p.get("name")}
    exact = [p for p in unique.values()
             if re.search(r"(?<!\w)" + re.escape(normalized(p["name"])) + r"(?!\w)",
                          normalized_query)]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    surname = [p for p in unique.values()
               if len(normalized(p["name"]).split()[-1]) >= 4
               and re.search(r"(?<!\w)" +
                             re.escape(normalized(p["name"]).split()[-1]) + r"(?!\w)",
                             normalized_query)]
    return surname[0] if len(surname) == 1 else None


def resolve_player_in_games(query: str, games: list[dict], *,
                            roster_fetch=fetch_roster, max_teams: int = 30) -> dict | None:
    ids = []
    for game in games:
        if game.get("sport") != "NBA":
            continue
        for key in ("away_team_id", "home_team_id"):
            value = str(game.get(key) or "")
            if re.fullmatch(r"\d{1,8}", value) and value not in ids:
                ids.append(value)
    if not ids:
        return None

    def safely_read(team_id: str) -> list[dict]:
        try:
            return roster_fetch(team_id).get("athletes", [])
        except (PlayerSourceError, ValueError, OSError):
            return []

    # At most five concurrent network reads, bounded to 30 NBA rosters.
    with ThreadPoolExecutor(max_workers=5) as pool:
        all_players = [player for team in pool.map(safely_read, ids[:max_teams])
                       for player in team]
    return resolve_player(query, all_players)


def _numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) and 0 <= number <= 200 else None


def parse_gamelog(payload: dict, stat: str, target_day: date) -> list[dict]:
    """Return documented regular-season games only; never include the target date."""
    if stat not in STATS:
        raise ValueError("Estadística no admitida")
    labels = payload.get("labels")
    metadata = payload.get("events")
    season_types = payload.get("seasonTypes")
    if not isinstance(labels, list) or not isinstance(metadata, dict) or not isinstance(season_types, list):
        return []
    normalized_labels = [str(v).upper() for v in labels]
    pos = next((normalized_labels.index(name) for name in STAT_LABELS[stat]
                if name in normalized_labels), None)
    if pos is None:
        return []
    seen = set()
    rows = []
    for season_type in season_types[:8]:
        if not isinstance(season_type, dict):
            continue
        title = normalized(str(season_type.get("displayName") or season_type.get("name") or ""))
        type_id = str(season_type.get("id") or season_type.get("type") or "")
        if "preseason" in title or "postseason" in title or "playoff" in title:
            continue
        if title and "regular" not in title and type_id != "2":
            continue
        if not title and type_id != "2":
            continue
        for category in season_type.get("categories", [])[:10]:
            if not isinstance(category, dict):
                continue
            for entry in category.get("events", [])[:200]:
                if not isinstance(entry, dict):
                    continue
                ident = str(entry.get("eventId") or "")
                if not ident or ident in seen:
                    continue
                event = metadata.get(ident)
                values = entry.get("stats")
                if not isinstance(event, dict) or not isinstance(values, list) or len(values) <= pos:
                    continue
                date_string = event.get("gameDate") or event.get("date")
                if not isinstance(date_string, str):
                    continue
                try:
                    starts = datetime.fromisoformat(date_string.replace("Z", "+00:00"))
                    if starts.tzinfo is None:
                        continue
                    day = starts.astimezone(MX).date()
                except ValueError:
                    continue
                if day >= target_day:
                    continue
                raw = values[pos]
                if stat == "3PM" and isinstance(raw, str) and "-" in raw:
                    raw = raw.split("-", 1)[0]
                score = _numeric(raw)
                if score is None:
                    continue
                seen.add(ident)
                opponent = event.get("opponent")
                opponent_name = (opponent.get("abbreviation") or opponent.get("displayName")
                                 if isinstance(opponent, dict) else "")
                rows.append({
                    "date": day.isoformat(), "value": score, "event_id": ident,
                    "opponent": opponent_name or "", "source": "ESPN gamelog",
                })
    return sorted(rows, key=lambda row: (row["date"], row["event_id"]), reverse=True)


def fetch_gamelog(player_id: str, as_of: date) -> dict:
    season = season_for(as_of)
    url = gamelog_url(player_id, season)
    data = _request_json(url)
    return {
        "payload": data, "source_url": url,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def summarize_prop(rows: list[dict], question: PlayerQuestion) -> dict:
    recent = rows[:10]
    if not recent:
        return {"games": 0, "last5": None, "last10": None, "historical_hits": None,
                "historical_rate": None, "pushes": 0}
    result = {
        "games": len(rows),
        "last5": round(mean(x["value"] for x in rows[:5]), 2),
        "last10": round(mean(x["value"] for x in recent), 2),
        "historical_hits": None, "historical_rate": None, "pushes": 0,
    }
    if question.line is not None and question.direction:
        hits = sum((r["value"] > question.line if question.direction == "over"
                    else r["value"] < question.line) for r in recent)
        pushes = sum(r["value"] == question.line for r in recent)
        decisions = len(recent) - pushes
        result.update({
            "historical_hits": hits,
            "historical_sample": decisions,
            "historical_rate": round(100 * hits / decisions, 1) if decisions else None,
            "pushes": pushes,
        })
    return result
