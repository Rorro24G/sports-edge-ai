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


# El consenso de Covers proviene de selecciones de participantes en concursos
# gratuitos; NO equivale a dinero real apostado en casinos de Las Vegas.
CONSENSUS_PAGES = {
    "NBA": "https://contests.covers.com/Consensus/TopConsensus/NBA/Overall",
    "NFL": "https://contests.covers.com/consensus/topconsensus/nfl/overall",
    "NHL": "https://contests.covers.com/consensus/topconsensus/nhl/overall",
}

PUBLIC_MONEY_EXPLANATION = "https://contests.covers.com/consensus/faq"


def consensus_link(league: str) -> str | None:
    """Enlace comprobado al consenso de concursos, no a splits de sportsbooks."""
    return CONSENSUS_PAGES.get(league)
