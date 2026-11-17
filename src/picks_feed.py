"""Combine Covers projections and ESPN fixtures without inventing prices or picks."""
from __future__ import annotations

from datetime import date

from .pick_context import match_espn_event


def live_picks_catalog(covers_events: list[dict], boards: dict[str, list[dict]],
                       target: date) -> list[dict]:
    """Show every verified game, preferring Covers where its game is identifiable.

    ESPN-only games are explicitly marked as having no Covers projection or odds.
    """
    selected = []
    matched_ids: set[tuple[str, str]] = set()
    day = target.isoformat()
    for game in covers_events:
        league = game.get("liga")
        if league not in ("NBA", "NFL", "NHL") or game.get("fecha_cdmx") != day:
            continue
        event = dict(game)
        event["origen"] = "Covers"
        event["estado"] = "PROGRAMADO"
        linked = match_espn_event(game, boards.get(league, []))
        if linked:
            event["espn_event_id"] = linked.get("event_id")
            event["estado"] = linked.get("status", "PROGRAMADO")
            matched_ids.add((league, str(linked.get("event_id"))))
        selected.append(event)
    for league, games in boards.items():
        if league not in ("NBA", "NFL", "NHL"):
            continue
        for game in games:
            event_id = str(game.get("event_id", ""))
            if (league, event_id) in matched_ids:
                continue
            if not game.get("away") or not game.get("home") or not game.get("local_time"):
                continue
            selected.append({
                "liga": league,
                "partido": game["away"] + " @ " + game["home"],
                "fecha_cdmx": day,
                "hora_cdmx": game["local_time"],
                "estado": game.get("status", "PROGRAMADO"),
                "origen": "ESPN",
                "fuente": game.get("source_url", ""),
                "proyeccion_visitante": None,
                "proyeccion_local": None,
                "momio_visitante": None,
                "momio_local": None,
                "espn_event_id": event_id,
            })
    return sorted(selected, key=lambda row: (
        row.get("hora_cdmx", "99:99"), row["liga"], row["partido"]))


def pick_catalog_rows(events: list[dict]) -> list[dict]:
    """UI data: original moneylines, not projection percentages disguised as odds."""
    rows = []
    for game in events:
        away, _, home = game["partido"].partition(" @ ")
        away_ml = game.get("momio_visitante")
        home_ml = game.get("momio_local")
        rows.append({
            "Liga": game["liga"],
            "Partido": away + " vs " + home,
            "Hora CDMX": game["hora_cdmx"],
            "ML visitante": str(away_ml) if away_ml else "—",
            "ML local": str(home_ml) if home_ml else "—",
            "Estado": game.get("estado", "—"),
            "Fuente": game.get("origen", "Covers"),
        })
    return rows
