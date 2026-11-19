"""Interpretación conservadora de consultas en español para la interfaz web.

No inventa eventos, cuotas ni probabilidades. Separa fecha/deportes solicitados
de cualquier resultado procedente de fuentes deportivas verificadas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
import unicodedata
from zoneinfo import ZoneInfo

MEXICO_TZ = ZoneInfo("America/Mexico_City")
SPORTS = ("NFL", "NBA", "NHL", "ATP", "WTA")
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
PATTERNS = {
    "NFL": r"\b(?:nfl|futbol americano)\b",
    "NBA": r"\b(?:nba|basquetbol|basquet|basketball)\b",
    "NHL": r"\b(?:nhl|hockey)\b",
    "ATP": r"\batp\b",
    "WTA": r"\bwta\b",
}


def normalized(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(ch)
    )


@dataclass(frozen=True)
class Request:
    target_date: date
    sports: tuple[str, ...]
    wants_parlay: bool
    wants_picks: bool


def interpret_request(text: str, *, now: datetime | None = None) -> Request:
    """Admite fechas explícitas y relativas; una fecha explícita tiene prioridad."""
    if now is None:
        now = datetime.now(MEXICO_TZ)
    today = now.astimezone(MEXICO_TZ).date() if now.tzinfo else now.date()
    query = normalized(text)
    target = today

    iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", query)
    named = re.search(
        r"\b(\d{1,2})\s+(?:de\s+)?("
        + "|".join(MONTHS)
        + r")(?:\s+(?:de\s+)?(20\d{2}))?\b", query
    )
    slash = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", query)
    if iso:
        target = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    elif slash:
        target = date(int(slash.group(3)), int(slash.group(2)), int(slash.group(1)))
    elif named:
        target = date(int(named.group(3) or today.year), MONTHS[named.group(2)], int(named.group(1)))
    elif re.search(r"\bpasado manana\b", query):
        target = today + timedelta(days=2)
    elif re.search(r"\bmanana\b", query):
        target = today + timedelta(days=1)

    found = [sport for sport, pattern in PATTERNS.items() if re.search(pattern, query)]
    if re.search(r"\btenis\b", query):
        found.extend(["ATP", "WTA"])
    chosen = tuple(s for s in SPORTS if s in set(found)) if found else SPORTS
    return Request(
        target_date=target,
        sports=chosen,
        wants_parlay=bool(re.search(r"\b(?:parlay|combinada|combinado|parlays)\b", query)),
        wants_picks=bool(re.search(r"\b(?:pick|picks|apuesta|apuestas|seleccion|selecciones)\b", query)),
    )
