"""Lectura auditable de calendarios: nunca equiparar una copia con una API en vivo."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "calendario_2026-11-13_15.json"
ET = ZoneInfo("America/New_York")
MX = ZoneInfo("America/Mexico_City")
SUPPORTED_SPORTS = frozenset({"NBA", "NFL", "NHL"})


@dataclass(frozen=True)
class ScheduleResult:
    games: tuple[dict, ...]
    date_covered: bool
    supported_sports: tuple[str, ...]
    missing_sports: tuple[str, ...]
    checked_date: str
    source_type: str = "COPIA_ESTATICA_NO_TIEMPO_REAL"


def load_fixture(path: Path = FIXTURE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise ValueError("Formato de calendario no válido")
    return data


def local_game(game: dict) -> dict:
    kickoff = datetime.fromisoformat(
        f"{game['date_et']}T{game['time_et']}"
    ).replace(tzinfo=ET).astimezone(MX)
    return {
        "sport": game["sport"],
        "away": game["away"],
        "home": game["home"],
        "local_date": kickoff.date(),
        "local_time": kickoff.strftime("%H:%M"),
        "source_url": game["source_url"],
        "market_status": game.get("market_status", "SIN_CUOTAS_VERIFICADAS"),
        "prediction_status": game.get("prediction_status", "SIN_MODELO_VALIDADO"),
    }


def find_games(fixture: dict, target: date, sports: tuple[str, ...]) -> ScheduleResult:
    events = fixture["events"]
    requested = tuple(dict.fromkeys(sports))
    supported = tuple(s for s in requested if s in SUPPORTED_SPORTS)
    missing = tuple(s for s in requested if s not in SUPPORTED_SPORTS)
    dates_et = [
        date.fromisoformat(game["date_et"])
        for game in events
    ]
    # This particular fixture covers complete ET dates, not arbitrary future days.
    covered = bool(dates_et and min(dates_et) <= target <= max(dates_et))
    rows = [local_game(game) for game in events]
    matched = tuple(sorted(
        (row for row in rows if row["local_date"] == target and row["sport"] in supported),
        key=lambda row: (row["local_time"], row["sport"], row["home"]),
    ))
    return ScheduleResult(
        games=matched,
        date_covered=covered,
        supported_sports=supported,
        missing_sports=missing,
        checked_date=fixture.get("checked_date", "desconocida"),
    )
