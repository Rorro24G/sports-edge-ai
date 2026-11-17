"""Prioriza un partido mencionado por el usuario, sin inventar coincidencias."""

from __future__ import annotations
import re

from .web_query import normalized


def _terms(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", normalized(text))
            if len(token) >= 3}


def rank_matches(rows: list[dict], question: str) -> list[dict]:
    """Mantiene todos los encuentros, pero presenta primero los más relevantes.

    No depende de un catálogo privado de equipos. Los nombres encontrados en
    Covers se comparan directamente con las palabras de la pregunta.
    """
    question_words = _terms(question)
    ignored = {
        "hoy", "manana", "ayer", "picks", "pick", "partido", "partidos",
        "dame", "quiero", "analiza", "analizar", "contra", "entre",
        "de", "del", "los", "las", "con", "para", "equipo", "equipos",
        "nba", "nfl", "nhl", "atp", "wta",
    }
    meaningful = question_words - ignored

    def score(row: dict) -> tuple[int, int]:
        matchup = row.get("partido", "")
        sides = matchup.split(" @ ", 1)
        if len(sides) != 2:
            return (0, 0)
        away, home = (_terms(side) for side in sides)
        away_hits = len(away & meaningful)
        home_hits = len(home & meaningful)
        both = int(away_hits > 0 and home_hits > 0)
        return (both, away_hits + home_hits)

    return sorted(rows, key=score, reverse=True)

def verified_market_rows(game: dict, rows: list[dict]) -> list[dict]:
    """Asocia cuotas sólo si ambos equipos coinciden, misma liga y hora.

    Rechaza coincidencias ambiguas (nombres genéricos o dos eventos candidatos)
    antes de atribuir momios a un partido concreto.
    """
    matchup = game.get("partido", "")
    parts = matchup.split(" @ ", 1)
    if len(parts) != 2:
        return []
    away, home = (_terms(name) for name in parts)
    if not away or not home or not game.get("fecha_cdmx"):
        return []
    league = game.get("liga")
    start = game.get("hora_cdmx")
    by_event = {}
    for row in rows:
        if row.get("sport") != league or row.get("start_local") != start:
            continue
        if row.get("date_local") != game["fecha_cdmx"]:
            continue
        sides = str(row.get("event", "")).split(" vs ")
        if len(sides) != 2:
            continue
        full_away, full_home = (_terms(side) for side in sides)
        # La ciudad de Covers debe estar presente en el nombre completo.
        if not (away <= full_away and home <= full_home):
            continue
        key = (row["event"], row["start_local"])
        by_event.setdefault(key, []).append(row)
    # Sin identidad inequívoca, no atribuimos un mercado.
    if len(by_event) != 1:
        return []
    return next(iter(by_event.values()))


# Words describing the request, not a team. Team matching never treats these
# as evidence that a specific game was requested.
_QUERY_FILLER = {
    "hoy", "manana", "ayer", "picks", "pick", "partido", "partidos",
    "dame", "quiero", "analiza", "analizar", "contra", "entre", "equipo",
    "equipos", "juego", "juegos", "del", "los", "las", "con", "para",
    "nba", "nfl", "nhl", "atp", "wta", "hockey", "basquetbol",
    "futbol", "americano", "este", "esta", "que", "son", "cuales",
    "mejores", "probabilidades", "momios", "noticias", "lesiones",
    "estadisticas", "fecha", "calendario", "todos", "todas",
    "noviembre", "diciembre", "octubre", "enero", "febrero", "marzo",
    "abril", "mayo", "junio", "julio", "agosto", "septiembre",
}

# Alias frecuentes cuando Covers usa ciudades y el usuario usa apodos.
# La coincidencia de ciudades ambiguas (p. ej., Lakers / Clippers)
# exige que el resto de la consulta identifique un único encuentro.
_NICKNAME_CITY = {
    "lakers": ("los", "angeles"), "clippers": ("los", "angeles"),
    "warriors": ("golden", "state"), "celtics": ("boston",),
    "knicks": ("new", "york"), "nets": ("brooklyn",),
    "sixers": ("philadelphia",), "76ers": ("philadelphia",),
    "raptors": ("toronto",), "bulls": ("chicago",),
    "heat": ("miami",), "cavaliers": ("cleveland",),
    "bucks": ("milwaukee",), "nuggets": ("denver",),
    "thunder": ("oklahoma", "city"), "spurs": ("san", "antonio"),
    "rockets": ("houston",), "mavericks": ("dallas",),
    "suns": ("phoenix",), "kings": ("sacramento",),
    "timberwolves": ("minnesota",), "grizzlies": ("memphis",),
    "pelicans": ("new", "orleans"), "pistons": ("detroit",),
    "wizards": ("washington",), "pacers": ("indiana",),
    "magic": ("orlando",), "hawks": ("atlanta",),
    "jazz": ("utah",), "blazers": ("portland",),
    "trail": ("portland",), "hornets": ("charlotte",),
    "eagles": ("philadelphia",), "chiefs": ("kansas", "city"),
    "cowboys": ("dallas",), "packers": ("green", "bay"),
    "ravens": ("baltimore",), "steelers": ("pittsburgh",),
    "bills": ("buffalo",), "dolphins": ("miami",),
    "patriots": ("new", "england"), "49ers": ("san", "francisco"),
    "bruins": ("boston",), "canadiens": ("montreal",),
    "maple": ("toronto",), "oilers": ("edmonton",),
    "penguins": ("pittsburgh",),
}
_DATE_PART = {"20", "2026", "2027", "2028", "2029", "2030"}


def _requested_tokens(text: str) -> set[str]:
    return _terms(text) - _QUERY_FILLER - _DATE_PART - {"2025", "2024"}


def _side_matches(requested: set[str], game_side: str) -> bool:
    side = _terms(game_side)
    if requested & side:
        return True
    for word in requested:
        city = _NICKNAME_CITY.get(word)
        if city and set(city) <= side:
            return True
    return False


def relevant_matches(rows: list[dict], question: str) -> tuple[list[dict], bool]:
    """Returns (possible games, specific_team_requested).

    Broad questions list every game. For queries naming teams, only games
    meeting that request are returned, never an unrelated first result.
    Explicit 'contra/vs' requires *both* teams, in either home/away order.
    """
    query = normalized(question)
    # Strip common date formats before finding an explicit two-team query.
    query = re.sub(r"\\b20\\d{2}-\\d{2}-\\d{2}\\b", " ", query)
    explicit = re.search(r"(.+?)\\s+(?:vs\\.?|versus|contra|@)\\s+(.+)", query)
    if explicit:
        first = _requested_tokens(explicit.group(1))
        second = _requested_tokens(explicit.group(2))
        if first and second:
            found = []
            for game in rows:
                sides = str(game.get("partido", "")).split(" @ ", 1)
                if len(sides) != 2:
                    continue
                away, home = sides
                if ((_side_matches(first, away) and _side_matches(second, home))
                        or (_side_matches(first, home) and _side_matches(second, away))):
                    found.append(game)
            return found, True

    requested = _requested_tokens(query)
    if not requested:
        return list(rows), False
    found = []
    for game in rows:
        sides = str(game.get("partido", "")).split(" @ ", 1)
        if len(sides) != 2:
            continue
        if any(_side_matches({word}, side) for word in requested for side in sides):
            found.append(game)
    return found, True
