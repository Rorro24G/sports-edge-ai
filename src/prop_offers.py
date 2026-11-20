"""Verifica cuotas de props NBA por evento exacto, jugador, línea y operador.

Fuente opcional: The Odds API v4. Nunca busca en todos los encuentros ni consume
créditos sin una clave ya configurada y una pregunta con línea y dirección.
Las proyecciones/porcentajes de Covers NO son momios americanos.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
import re

from .odds_api import _fetch, OddsAPIError
from .web_query import normalized
from .pick_context import _team_tokens

MX = ZoneInfo("America/Mexico_City")
MARKET_KEYS = {
    "PTS": "player_points", "REB": "player_rebounds",
    "AST": "player_assists", "3PM": "player_threes",
}
BOOK_REGIONS = ("us", "us2", "eu", "uk", "au")


def _timestamp(text):
    if not isinstance(text, str):
        return None
    try:
        result = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def _american(value):
    if isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number != number.to_integral_value():
        return None
    if abs(number) < 100 or abs(number) > 100_000:
        return None
    return int(number)


def _same_team(espn_name, api_name):
    left, right = _team_tokens(espn_name), _team_tokens(api_name)
    if not left or not right:
        return False
    # Reject superficial city-only overlap (e.g. LA Lakers vs LA Clippers).
    return left <= right or right <= left if len(left & right) >= 2 else left == right


def _local_start(event):
    dt = _timestamp(event.get("commence_time"))
    return dt.astimezone(MX) if dt else None


def select_single_event(events: list[dict], game: dict, target: date,
                        *, now: datetime | None = None) -> dict | None:
    """Both exact sides, date and time; ambiguity fails closed."""
    clock = now or datetime.now(timezone.utc)
    matches = []
    for event in events:
        if not isinstance(event, dict):
            continue
        start = _local_start(event)
        if start is None or start.date() != target or start <= clock.astimezone(MX):
            continue
        if start.strftime("%H:%M") != str(game.get("local_time") or ""):
            continue
        if (_same_team(game.get("away", ""), event.get("away_team", ""))
                and _same_team(game.get("home", ""), event.get("home_team", ""))
                and isinstance(event.get("id"), str)
                and re.fullmatch(r"[A-Za-z0-9_-]{6,100}", event["id"])):
            matches.append(event)
    return matches[0] if len(matches) == 1 else None


def extract_exact_prop_offers(event_data: dict, *, player_name: str,
                              stat: str, direction: str, line: float,
                              now: datetime | None = None) -> list[dict]:
    """Keep only quotes for identical player + market + side + numeric line."""
    if stat not in MARKET_KEYS or direction not in ("over", "under"):
        return []
    clock = now or datetime.now(timezone.utc)
    start = _timestamp(event_data.get("commence_time"))
    if start is None or start <= clock:
        return []
    try:
        expected = Decimal(str(line))
        if not expected.is_finite() or expected <= 0:
            return []
    except (TypeError, ValueError, InvalidOperation):
        return []
    results = []
    for book in event_data.get("bookmakers", [])[:100]:
        if not isinstance(book, dict) or not str(book.get("title", "")).strip():
            continue
        for market in book.get("markets", [])[:80]:
            if not isinstance(market, dict) or market.get("key") != MARKET_KEYS[stat]:
                continue
            stamp = _timestamp(market.get("last_update") or book.get("last_update"))
            if stamp is None:
                continue
            age_seconds = (clock - stamp).total_seconds()
            if age_seconds < -90 or age_seconds > 90 * 60:
                continue
            for outcome in market.get("outcomes", [])[:100]:
                if not isinstance(outcome, dict):
                    continue
                if normalized(str(outcome.get("description") or "")) != normalized(player_name):
                    continue
                if normalized(str(outcome.get("name") or "")) != direction:
                    continue
                try:
                    point = Decimal(str(outcome.get("point")))
                except (InvalidOperation, ValueError, TypeError):
                    continue
                if point != expected:
                    continue
                price = _american(outcome.get("price"))
                if price is None:
                    continue
                results.append({
                    "evento_proveedor": event_data.get("id"),
                    "inicio_utc": start.astimezone(timezone.utc).isoformat(),
                    "consultado_utc": clock.astimezone(timezone.utc).isoformat(),
                    "jugador": player_name,
                    "mercado": MARKET_KEYS[stat],
                    "direccion": direction,
                    "linea": str(point),
                    "momio_americano": price,
                    "casa": str(book["title"])[:90],
                    "actualizado_utc": stamp.astimezone(timezone.utc).isoformat(),
                    "fuente": "The Odds API",
                    "tipo": "COTIZACION_CON_PROVEEDOR",
                })
    return sorted(results, key=lambda r: (-r["momio_americano"], r["casa"]))


def fetch_player_prop_offers(api_key: str, *, game: dict, target: date,
                              player_name: str, stat: str, direction: str,
                              line: float, region: str = "us") -> list[dict]:
    """At most two API calls, only on explicit player+line requests."""
    if not api_key:
        return []
    if stat not in MARKET_KEYS or direction not in ("over", "under"):
        return []
    if region not in BOOK_REGIONS:
        raise ValueError("Región de mercado inválida")
    if game.get("sport") != "NBA":
        return []
    if not player_name or not (0 < line <= 200):
        return []
    clock = datetime.now(timezone.utc)
    if target < clock.astimezone(MX).date():
        return []
    items = _fetch("sports/basketball_nba/events", api_key, dateFormat="iso")
    if not isinstance(items, list):
        raise OddsAPIError("El proveedor no devolvió eventos válidos")
    matched = select_single_event(items, game, target, now=clock)
    if matched is None:
        return []
    data = _fetch(
        "sports/basketball_nba/events/" + matched["id"] + "/odds",
        api_key, regions=region, markets=MARKET_KEYS[stat],
        oddsFormat="american", dateFormat="iso",
    )
    if not isinstance(data, dict):
        raise OddsAPIError("El proveedor no devolvió mercados válidos")
    if data.get("id") != matched["id"]:
        raise OddsAPIError("Identidad de evento inconsistente")
    return extract_exact_prop_offers(
        data, player_name=player_name, stat=stat,
        direction=direction, line=line, now=clock,
    )

