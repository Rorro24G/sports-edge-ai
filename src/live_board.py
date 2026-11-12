"""Consulta de calendarios NBA/NFL/NHL al solicitar una fecha.

Esta fuente ESPN es un endpoint web sin contrato de API comercial; puede cambiar
sin aviso. No contiene cotizaciones ni pronosticos. Conservar URL y hora de consulta.
"""
from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo
import json

LOCAL = ZoneInfo("America/Mexico_City")
SPORT_PATH = {
    "NBA": ("basketball", "nba"),
    "NFL": ("football", "nfl"),
    "NHL": ("hockey", "nhl"),
}
class CalendarSourceError(RuntimeError):
    pass

def scoreboard_url(sport: str, day: date) -> str:
    if sport not in SPORT_PATH:
        raise ValueError("La liga no tiene calendario ESPN conectado")
    category, league = SPORT_PATH[sport]
    return (
        "https://site.api.espn.com/apis/site/v2/sports/"
        + category + "/" + league + "/scoreboard?"
        + urlencode({"dates": day.strftime("%Y%m%d"), "limit": 100})
    )

def normalize_scoreboard(payload: dict, sport: str, day: date) -> list[dict]:
    rows = []
    for event in payload.get("events", []):
        try:
            starts = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
            local = starts.astimezone(LOCAL)
            if local.date() != day:
                continue
            competition = event["competitions"][0]
            competitors = competition["competitors"]
            home = next(c for c in competitors if c["homeAway"] == "home")
            away = next(c for c in competitors if c["homeAway"] == "away")
            state = event.get("status", {}).get("type", {}).get("state", "unknown")
            home_name = home["team"]["displayName"]
            away_name = away["team"]["displayName"]
            if not home_name or not away_name:
                continue
            links = event.get("links") or []
            game_link = next((l.get("href") for l in links if l.get("href", "").startswith("https://")), "")
            rows.append({
                "sport": sport,
                "away": away_name,
                "home": home_name,
                "local_date": local.date(),
                "local_time": local.strftime("%H:%M"),
                "status": state.upper(),
                "source_url": game_link or "https://www.espn.com/",
                "event_id": str(event.get("id", "")),
                "market_status": "SIN_CUOTAS_VERIFICADAS",
                "prediction_status": "SIN_MODELO_VALIDADO",
                "source_name": "ESPN scoreboard",
            })
        except (KeyError, ValueError, TypeError, StopIteration, IndexError):
            continue
    return sorted(rows, key=lambda g:(g["local_time"], g["home"]))

def fetch_scoreboard(sport: str, day: date) -> dict:
    # Los eventos nocturnos pueden figurar en la jornada UTC siguiente.
    # Consultar ambas fechas evita perder partidos nocturnos de México.
    urls = [scoreboard_url(sport, day + timedelta(days=offset)) for offset in (0, 1)]
    merged = {}
    for url in urls:
        request = Request(url, headers={"User-Agent":"SportsEdgeAI/1.0","Accept":"application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.load(response)
        except (OSError, HTTPError, URLError, ValueError, TimeoutError):
            raise CalendarSourceError("No se pudo consultar el calendario de " + sport) from None
        if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            raise CalendarSourceError("Respuesta de calendario no válida de " + sport)
        for item in normalize_scoreboard(payload, sport, day):
            merged[item["event_id"] or (item["away"], item["home"])] = item
    return {"games": sorted(merged.values(), key=lambda row: (row["local_time"], row["home"])),
            "url": urls[0], "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "ESPN scoreboard"}
