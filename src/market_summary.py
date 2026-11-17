"""Porcentaje implícito de momios, distinto de pronósticos y dinero apostado."""
from __future__ import annotations
from math import isfinite


def implied_percent(price: str | int | float | None) -> float | None:
    """Devuelve porcentaje de equilibrio para una cuota americana válida."""
    if price is None or isinstance(price, bool):
        return None
    if isinstance(price, str):
        price = price.strip()
        if not price or not (price.lstrip("+-").isdigit()):
            return None
    try:
        odd = float(price)
    except (ValueError, TypeError, OverflowError):
        return None
    if not isfinite(odd) or abs(odd) < 100 or not odd.is_integer():
        return None
    return round((100 / (odd + 100) if odd > 0 else (-odd) / (100 - odd)) * 100, 2)


def game_market_probabilities(game: dict) -> dict[str, float | None]:
    return {
        "visitante": implied_percent(game.get("momio_visitante")),
        "local": implied_percent(game.get("momio_local")),
    }
