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
