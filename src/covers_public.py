"""Consulta puntual de proyecciones públicas de Covers para análisis personal.

No utiliza sesiones, APIs privadas, evasión de controles ni almacenamiento de
contenido de terceros. Al fallar una lectura se informa, sin rellenar datos.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import re

from .covers_reference import COVERS_PAGES

ET = ZoneInfo("America/New_York")
MX = ZoneInfo("America/Mexico_City")
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_DATE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),\s+(20\d{2})\b", re.I)
_KICKOFF = re.compile(r"\b(Today|[A-Za-z]{3}\.?\s+\d{1,2})\s*[•·]\s*(\d{1,2}:\d{2})\s*(AM|PM)\s*ET\b", re.I)
_MATCHUP = re.compile(r"^([A-Za-z][A-Za-z .'-]{1,50}?)\s*@\s*([A-Za-z][A-Za-z .'-]{1,50})$")
_SCORE = re.compile(r"(\d+(?:\.\d+)?)\s*@\s*[^\d]{0,5}(\d+(?:\.\d+)?)")
_TOTAL = re.compile(r"\b[ou]\d+(?:\.\d+)?\s*[+-]\d{3,4}\b", re.I)
_SPREAD = re.compile(r"(?<![\w.])[+-]\d+(?:\.\d+)?\s+[+-]\d{3,4}\b")
_PROB = re.compile(r"\b(?:100|\d{1,2})%")
_BLOCK = {"div", "p", "section", "article", "li", "tr", "table",
          "h1", "h2", "h3", "h4", "h5", "h6"}


class CoversSourceError(RuntimeError):
    pass


class _ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        elif not self.skip and tag in _BLOCK:
            self.parts.append("\n")
        elif not self.skip and tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip - 1)
        elif not self.skip and (tag in _BLOCK or tag in {"td", "th"}):
            self.parts.append("\n" if tag in _BLOCK else " | ")

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(" " + data.strip() + " ")

    def lines(self):
        return [re.sub(r"\s+", " ", row).strip(" |")
                for row in "".join(self.parts).splitlines()
                if row.strip(" | \t\r\n")]


def _published_date(text: str):
    # Anclar la fecha al encabezado editorial, no a artículos secundarios.
    head = re.search(r"(?:Free (?:NBA|NHL) Expert|Free expert and computer picks|best NFL bets today).{0,170}",
                     text[:9000], re.I)
    match = _DATE.search(head.group(0)) if head else None
    if match is None:
        match = _DATE.search(text[:1800])
    if match is None:
        return None
    return date(int(match.group(3)), MONTHS[match.group(1)[:3].lower()], int(match.group(2)))


def _start_time(label: str, published: date) -> datetime | None:
    m = _KICKOFF.search(label)
    if not m:
        return None
    if m.group(1).lower() == "today":
        game_day = published
    else:
        d = m.group(1).replace(".", "").split()
        month = MONTHS.get(d[0][:3].lower())
        if not month:
            return None
        year = published.year
        if published.month == 12 and month == 1:
            year += 1
        game_day = date(year, month, int(d[1]))
    clock = datetime.strptime(m.group(2) + " " + m.group(3).upper(), "%I:%M %p")
    return datetime(game_day.year, game_day.month, game_day.day,
                    clock.hour, clock.minute, tzinfo=ET)


def parse_public_picks(html: str, league: str, target: date) -> dict:
    """Extrae únicamente partidos/proyecciones visibles; cero datos inventados."""
    if league not in COVERS_PAGES:
        raise ValueError("Liga no admitida")
    reader = _ReadableHTML()
    reader.feed(html)
    lines = reader.lines()
    visible = "\n".join(lines)
    published = _published_date(visible)
    if published is None:
        raise CoversSourceError("Covers no devolvió un encabezado con fecha reconocible")
    events = []
    for index, line in enumerate(lines):
        match = _MATCHUP.fullmatch(line)
        if not match or "http" in line.lower():
            continue
        # El partido va seguido de su hora y bloque de pronóstico.
        near = " ".join(lines[index + 1:index + 7])
        start = _start_time(near, published)
        if not start or start.astimezone(MX).date() != target:
            continue
        next_game = next((j for j in range(index + 1, len(lines))
                          if _MATCHUP.fullmatch(lines[j])), len(lines))
        block = lines[index + 1:min(next_game, index + 45)]
        details = " ".join(block)
        if "Predicted Score" not in details:
            continue
        score_area = details.split("Predicted Score", 1)[1][:260]
        score = _SCORE.search(score_area)
        predicted_away = float(score.group(1)) if score else None
        predicted_home = float(score.group(2)) if score else None
        # Solo valores del bloque del encuentro, no de artículos posteriores.
        odds_area = details.split("Prediction & Game Odds", 1)[-1][:900] \
            if "Prediction & Game Odds" in details else ""
        totals = tuple(dict.fromkeys(_TOTAL.findall(odds_area)))[:4]
        spreads = tuple(dict.fromkeys(_SPREAD.findall(odds_area)))[:4]
        probabilities = tuple(dict.fromkeys(_PROB.findall(odds_area)))[:6]
        events.append({
            "liga": league,
            "partido": match.group(1).strip() + " @ " + match.group(2).strip(),
            "fecha_cdmx": start.astimezone(MX).strftime("%Y-%m-%d"),
            "hora_cdmx": start.astimezone(MX).strftime("%H:%M"),
            "proyeccion_visitante": predicted_away,
            "proyeccion_local": predicted_home,
            "totales_publicados": ", ".join(totals) if totals else None,
            "spreads_publicados": ", ".join(spreads) if spreads else None,
            "probabilidades_publicadas": ", ".join(probabilities) if probabilities else None,
            "fuente": COVERS_PAGES[league],
        })
    return {"league": league, "events": events, "page_date": published.isoformat(),
            "source_url": COVERS_PAGES[league]}


def fetch_public_picks(league: str, target: date) -> dict:
    """Una solicitud HTML normal, sin seguir enlaces privados o eludir bloqueos."""
    url = COVERS_PAGES.get(league)
    if not url:
        raise ValueError("Liga no admitida")
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; SportsEdgeAI-personal/1.0)",
        "Accept": "text/html",
    })
    try:
        with urlopen(request, timeout=12) as response:
            if "html" not in response.headers.get("Content-Type", ""):
                raise CoversSourceError("Covers no devolvió HTML")
            payload = response.read(3_000_001)
            if len(payload) > 3_000_000:
                raise CoversSourceError("La respuesta de Covers superó el tamaño permitido")
            html = payload.decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise CoversSourceError("Covers devolvió HTTP " + str(exc.code)) from None
    except (URLError, TimeoutError, OSError):
        raise CoversSourceError("No se pudo consultar Covers desde el servidor") from None
    parsed = parse_public_picks(html, league, target)
    parsed["checked_at_utc"] = datetime.now(timezone.utc).isoformat()
    return parsed
