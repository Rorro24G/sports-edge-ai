"""Referencias oficiales de Covers por liga; no realiza extracción automatizada."""
from __future__ import annotations

COVERS_PAGES = {
    "NBA": "https://www.covers.com/picks/nba",
    "NFL": "https://www.covers.com/picks/nfl",
    "NHL": "https://www.covers.com/picks/nhl",
}


def picks_links(sports) -> tuple[tuple[str, str], ...]:
    """Devuelve enlaces para las ligas disponibles, sin inventar URLs ni datos."""
    chosen = set(sports)
    return tuple((league, url) for league, url in COVERS_PAGES.items()
                 if league in chosen)
