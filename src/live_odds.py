"""Vista de momios en tiempo real de The Odds API: no calcula picks.

Una clave de SOLO LECTURA se configura en secretos de hosting. Si falta, no
descarga precios. Limitamos cantidad de ligas/mercados para cuidar la cuota.
"""
from __future__ import annotations
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from .odds_api import _fetch, SPORTS, OddsAPIError

LOCAL = ZoneInfo("America/Mexico_City")
MARKETS = ("h2h", "spreads", "totals")
REGIONS = ("us", "us2", "uk", "eu", "au")

def odds_for_day(api_key: str, sports: tuple[str,...], target: date, *,
                 region: str = "us") -> list[dict]:
    if not api_key:
        return []
    if region not in REGIONS:
        raise ValueError("Región inválida")
    if len(sports) > 5:
        raise ValueError("Se solicitaron demasiadas ligas")
    result = []
    for sport in sports:
        sport_key = SPORTS.get(sport)
        if sport_key is None:
            continue
        # 3 mercados x 1 region x deporte = 3 unidades posibles; el proveedor
        # puede cobrar según mercados efectivamente presentes.
        events = _fetch("sports/"+sport_key+"/odds", api_key,
                        regions=region, markets="h2h,spreads,totals",
                        oddsFormat="american", dateFormat="iso")
        for ev in events:
            try:
                starts = datetime.fromisoformat(ev["commence_time"].replace("Z","+00:00"))
                if starts.astimezone(LOCAL).date() != target:
                    continue
                if starts <= datetime.now(timezone.utc):
                    continue
                event_name = f'{ev.get("away_team","")} vs {ev.get("home_team","")}'
                for book in ev.get("bookmakers", []):
                    book_name = str(book.get("title",""))
                    for market in book.get("markets", []):
                        if market.get("key") not in MARKETS:
                            continue
                        updated = str(market.get("last_update") or book.get("last_update") or "")
                        for outcome in market.get("outcomes", []):
                            if not isinstance(outcome.get("price"),(int,float)):
                                continue
                            result.append({
                                "sport": sport, "event": event_name,
                                "start_local": starts.astimezone(LOCAL).strftime("%H:%M"),
                                "market": market["key"],
                                "pick": str(outcome.get("name","")),
                                "line": outcome.get("point"),
                                "book": book_name,
                                "odds": outcome["price"],
                                "updated_at": updated,
                                "source": "The Odds API",
                            })
            except (TypeError, ValueError, KeyError):
                continue
    return result
