"""Informe diario privado de Picks: fuentes públicas, sin apuestas automáticas.

Genera JSON/Markdown en disco para guardar como artefactos privados de Actions.
No publica datos externos como propios; no genera recomendaciones de valor
hasta tener probabilidades calibradas contra resultados reales.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .covers_public import CoversSourceError, fetch_public_picks
from .live_board import CalendarSourceError, fetch_scoreboard
from .live_odds import odds_for_day
from .odds_api import OddsAPIError
from .pick_context import ContextSourceError, fetch_summary, match_espn_event
from .market_summary import game_market_probabilities
from .match_report import verified_market_rows

LOCAL = ZoneInfo("America/Mexico_City")
LEAGUES = ("NBA", "NFL", "NHL")


def build_report(day: date, *, covers_fetch=fetch_public_picks,
                 board_fetch=fetch_scoreboard, summary_fetch=fetch_summary,
                 odds_fetch=odds_for_day, odds_key: str = "") -> dict:
    """Create a traceable daily snapshot, never silently substitute older dates."""
    result = {
        "date_cdmx": day.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "leagues": {},
        "pick_status": "SIN_MODELO_VALIDADO",
        "reason": "No existe una probabilidad predictiva propia calibrada y validada",
    }
    for league in LEAGUES:
        section = {
            "coverage": {"covers": "no_consultado", "espn": "no_consultado",
                         "odds": "sin_proveedor"},
            "events": [], "errors": [],
        }
        result["leagues"][league] = section
        try:
            covers = covers_fetch(league, day)
            # Only games on the exact Mexico calendar date.
            published = [g for g in covers.get("events", [])
                         if g.get("liga") == league and g.get("fecha_cdmx") == day.isoformat()]
            section["coverage"]["covers"] = "consultado"
        except (CoversSourceError, ValueError, OSError) as exc:
            published = []
            section["coverage"]["covers"] = "error"
            section["errors"].append("Covers: " + str(exc))
        try:
            board = board_fetch(league, day)
            schedule = board["games"]
            section["coverage"]["espn"] = "consultado"
        except (CalendarSourceError, ValueError, OSError, KeyError) as exc:
            schedule = []
            section["coverage"]["espn"] = "error"
            section["errors"].append("ESPN: " + str(exc))

        odds = []
        if odds_key:
            try:
                odds = odds_fetch(odds_key, (league,), day)
                section["coverage"]["odds"] = "consultado"
            except (OddsAPIError, ValueError, OSError) as exc:
                section["coverage"]["odds"] = "error"
                section["errors"].append("Momios externos: " + str(exc))

        for g in published:
            linked = match_espn_event(g, schedule) if schedule else None
            details = {
                "liga": league, "partido": g["partido"],
                "fecha_cdmx": g["fecha_cdmx"], "hora_cdmx": g["hora_cdmx"],
                "fuente_covers": g["fuente"],
                "proyeccion_covers": [g.get("proyeccion_visitante"),
                                     g.get("proyeccion_local")],
                "momios_covers": [g.get("momio_visitante"), g.get("momio_local")],
                "probabilidad_implicita_mercado": game_market_probabilities(g),
                "spreads_publicados": g.get("spreads_publicados"),
                "totales_publicados": g.get("totales_publicados"),
                "porcentajes_covers": g.get("probabilidades_publicadas"),
                "momios_casas": verified_market_rows(g, odds),
                "espn": None, "pick_propio": None,
                "estado_pick": "SIN_MODELO_VALIDADO",
            }
            if linked:
                context = {"evento": linked.get("event_id"),
                           "estado": linked.get("status"),
                           "fuente": linked.get("source_url")}
                try:
                    summary = summary_fetch(league, linked["event_id"])
                    context.update({
                        "lesiones": summary.get("injuries", []),
                        "lideres": summary.get("leaders", []),
                        "noticias": summary.get("news", []),
                        "consulta_utc": summary.get("checked_at_utc"),
                    })
                except (ContextSourceError, ValueError, OSError, KeyError) as exc:
                    context["error"] = str(exc)
                details["espn"] = context
            section["events"].append(details)

        # An empty Covers page does not erase a real ESPN schedule.
        linked_ids = {e["espn"]["evento"] for e in section["events"] if e.get("espn")}
        for game in schedule:
            if game.get("event_id") in linked_ids:
                continue
            section["events"].append({
                "liga": league,
                "partido": game["away"] + " @ " + game["home"],
                "fecha_cdmx": day.isoformat(), "hora_cdmx": game["local_time"],
                "fuente_espn": game.get("source_url"),
                "estado": game.get("status"),
                "datos_covers": "no_verificados_para_este_partido",
                "pick_propio": None, "estado_pick": "SIN_MODELO_VALIDADO",
            })
    return result


def render_markdown(report: dict) -> str:
    lines = [
        "# Picks — " + report["date_cdmx"] + " (CDMX)",
        "",
        "Generado: " + report["generated_at_utc"] + " UTC",
        "",
        "**Estado de recomendaciones propias: SIN MODELO VALIDADO.** "
        "Las cuotas y proyecciones externas no prueban rentabilidad.",
        "",
    ]
    for league, section in report["leagues"].items():
        lines.extend(["## " + league, "",
                      "Cobertura: " + ", ".join(
                          k + "=" + v for k, v in section["coverage"].items()), ""])
        for event in section["events"]:
            lines.append("- " + event["partido"] + " (" + event["hora_cdmx"] + " CDMX): "
                         + "sin pick propio validado")
        if not section["events"]:
            lines.append("- No se encontraron eventos verificables para esa fecha")
        for error in section["errors"]:
            lines.append("- Advertencia: " + error)
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD, por defecto hoy en CDMX")
    parser.add_argument("--output-dir", default="daily-output")
    args = parser.parse_args()
    day = date.fromisoformat(args.date) if args.date else datetime.now(LOCAL).date()
    report = build_report(day, odds_key=os.environ.get("ODDS_API_KEY", ""))
    directory = Path(args.output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "picks.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "resumen.md").write_text(render_markdown(report), encoding="utf-8")
    for league, section in report["leagues"].items():
        print(league, "partidos", len(section["events"]),
              "fuentes", section["coverage"], flush=True)
    print("INFORME_GENERADO", day.isoformat(),
          "SIN_MODELO_VALIDADO", flush=True)


if __name__ == "__main__":
    main()
