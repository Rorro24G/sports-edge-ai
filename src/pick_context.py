"""Contexto de un partido de Picks a partir del calendario y resumen de ESPN.

No calcula picks, interpreta estados médicos ni afirma que una lista vacía de
lesiones equivalga a jugadores sanos. Solo usa un evento cuya pareja de equipos
concuerde por ambos lados. No mezcla partidos ambiguos.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import re

from .live_board import SPORT_PATH
from .web_query import normalized

_ALIASES = (
    (r"\bn[.]?\s*y[.]?\b", "new york"),
    (r"\bl[.]?\s*a[.]?\b", "los angeles"),
    (r"\bst[.]\s+", "saint "),
)
_IGNORED = {"the", "de", "del", "vs", "at", "and", "fc", "sc"}


class ContextSourceError(RuntimeError):
    """ESPN no pudo entregar un resumen verificable."""


def _team_tokens(value: str) -> set[str]:
    name = normalized(value or "")
    for expression, replacement in _ALIASES:
        name = re.sub(expression, replacement, name)
    return {word for word in re.findall(r"[a-z0-9]+", name)
            if word not in _IGNORED and len(word) >= 2}


def match_espn_event(covers: dict, scoreboard_games: list[dict]) -> dict | None:
    """Exige coincidencia de ambos equipos y de la liga; no adivina."""
    name = covers.get("partido", "")
    if " @ " not in name:
        return None
    away, home = name.split(" @ ", 1)
    first = _team_tokens(away)
    second = _team_tokens(home)
    if not first or not second:
        return None
    possibilities = []
    for row in scoreboard_games:
        if row.get("sport") != covers.get("liga"):
            continue
        away_shared = first & _team_tokens(row.get("away", ""))
        home_shared = second & _team_tokens(row.get("home", ""))
        if not away_shared or not home_shared:
            continue
        score = len(away_shared) + len(home_shared)
        # Un horario coincidente ayuda a desempatar; sin ello no forzamos.
        if row.get("local_time") == covers.get("hora_cdmx"):
            score += 1
        possibilities.append((score, row))
    if not possibilities:
        return None
    possibilities.sort(key=lambda pair: pair[0], reverse=True)
    if len(possibilities) > 1 and possibilities[0][0] == possibilities[1][0]:
        return None
    return possibilities[0][1]


def _as_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("displayName", "fullName", "name", "description", "shortDisplayName"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()
    return ""


def parse_summary(payload: dict, *, url: str) -> dict:
    """Extrae solo campos publicados de ESPN, con límites de presentación."""
    if not isinstance(payload, dict):
        raise ContextSourceError("ESPN devolvió un resumen no válido")

    injuries: list[dict] = []
    raw_injuries = payload.get("injuries")
    if isinstance(raw_injuries, list):
        for group in raw_injuries[:12]:
            if not isinstance(group, dict):
                continue
            club = _as_text(group.get("team"))
            entries = group.get("injuries")
            if not isinstance(entries, list):
                entries = [group] if group.get("athlete") else []
            for entry in entries[:35]:
                if not isinstance(entry, dict):
                    continue
                athlete = (_as_text(entry.get("athlete"))
                           or _as_text(entry.get("player"))
                           or _as_text(entry.get("name")))
                status = _as_text(entry.get("status"))
                injury_type = _as_text(entry.get("type"))
                if not athlete or not status:
                    continue
                injuries.append({
                    "Equipo": club or "No especificado",
                    "Jugador": athlete,
                    "Estado ESPN": status,
                    "Motivo": injury_type or "No indicado",
                })
    leaders: list[dict] = []
    raw_leaders = payload.get("leaders")
    if isinstance(raw_leaders, list):
        for group in raw_leaders[:12]:
            if not isinstance(group, dict):
                continue
            club = _as_text(group.get("team"))
            categories = group.get("leaders")
            if not isinstance(categories, list):
                continue
            for category in categories[:8]:
                if not isinstance(category, dict):
                    continue
                category_name = _as_text(category)
                leaders_list = category.get("leaders")
                if not isinstance(leaders_list, list):
                    continue
                for leader in leaders_list[:1]:
                    if not isinstance(leader, dict):
                        continue
                    athlete = _as_text(leader.get("athlete"))
                    stat = _as_text(leader.get("displayValue"))
                    if athlete and stat:
                        leaders.append({
                            "Equipo": club or "No especificado",
                            "Categoría": category_name or "Líder",
                            "Jugador": athlete,
                            "Dato publicado": stat,
                        })

    venue = ""
    if isinstance(payload.get("gameInfo"), dict):
        venue = _as_text(payload["gameInfo"].get("venue"))
    return {
        "injuries": injuries,
        "leaders": leaders,
        "venue": venue,
        "source_url": url,
    }


def summary_url(league: str, event_id: str) -> str:
    if league not in SPORT_PATH:
        raise ValueError("Liga no disponible en ESPN")
    if not re.fullmatch(r"\d{5,15}", str(event_id)):
        raise ValueError("Identificador de evento no válido")
    category, slug = SPORT_PATH[league]
    return (f"https://site.api.espn.com/apis/site/v2/sports/"
            f"{category}/{slug}/summary?event={event_id}")


def fetch_summary(league: str, event_id: str) -> dict:
    """Consulta de solo lectura; errores explícitos, sin datos simulados."""
    url = summary_url(league, event_id)
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "SportsEdgeAI-personal/1.0",
    })
    try:
        with urlopen(req, timeout=10) as response:
            payload = response.read(5_000_001)
            if len(payload) > 5_000_000:
                raise ContextSourceError("ESPN devolvió demasiados datos")
            data = json.loads(payload)
    except HTTPError as exc:
        raise ContextSourceError(f"ESPN devolvió HTTP {exc.code}") from None
    except (URLError, OSError, TimeoutError, ValueError):
        raise ContextSourceError("ESPN no respondió con información válida") from None
    result = parse_summary(data, url=url)
    result["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    return result
