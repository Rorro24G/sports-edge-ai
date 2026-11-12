"""Adaptador mínimo de The Odds API v4 (https://the-odds-api.com/)."""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.the-odds-api.com/v4"
SPORTS = {
    "NBA": "basketball_nba",
    "NFL": "americanfootball_nfl",
    "NHL": "icehockey_nhl",
}


class OddsAPIError(RuntimeError):
    pass


def _fetch(endpoint: str, api_key: str, **params):
    query = urllib.parse.urlencode({"apiKey": api_key, **params})
    request = urllib.request.Request(
        f"{BASE}/{endpoint.lstrip('/')}?{query}",
        headers={"User-Agent": "SportsEdgeAI/0.1", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # No registrar la URL: contiene la credencial en el query string.
        raise OddsAPIError(f"Respuesta HTTP {exc.code} de The Odds API") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OddsAPIError(f"Error de red o de respuesta: {type(exc).__name__}") from None


def fetch_live_events(api_key: str, region: str = "us", max_tennis_keys: int = 4):
    """Consulta cuotas prepartido H2H; la disponibilidad depende del proveedor y del plan."""
    if not api_key:
        raise ValueError("Falta ODDS_API_KEY")
    if region not in {"us", "us2", "uk", "eu", "au"}:
        raise ValueError("Región no admitida")
    catalog = _fetch("sports", api_key)
    active = {item.get("key") for item in catalog if item.get("active")}
    selected = [(name, key) for name, key in SPORTS.items() if key in active]
    tennis_keys = [item.get("key") for item in catalog if item.get("active")
                   and item.get("group", "").lower() == "tennis"
                   and not item.get("has_outrights") and item.get("key")]
    selected.extend(("TENIS", key) for key in tennis_keys[:max_tennis_keys])
    events = []
    for sport_name, sport_key in selected:
        # Solo h2h: cuota asequible en créditos, sin apuestas en vivo.
        items = _fetch(f"sports/{urllib.parse.quote(sport_key)}/odds", api_key,
                       regions=region, markets="h2h", oddsFormat="american")
        for item in items:
            item["_sport_name"] = sport_name
            events.append(item)
    return events, [key for _, key in selected]
