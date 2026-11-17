"""Auditoría histórica del radar de Covers frente a MARCADORES FINALES ESPN.

Lee sólo pronósticos archivados antes del inicio y los liquida usando el
ID oficial del evento ESPN, no coincidencias difusas por nombre de equipo.
Un porcentaje observado NO es la probabilidad propia ni el ROI esperado.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from .live_board import fetch_scoreboard, CalendarSourceError
from .pick_reference import covers_projection
from .market_summary import implied_percent

LOCAL = ZoneInfo("America/Mexico_City")
MAX_HISTORY_BYTES = 1_500_000
FINAL_STATES = ("POST", "FINAL")
MONEY = Decimal("0.01")


def _parse_stamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else None


def _score(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        score = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return score if score.is_finite() and score >= 0 and score <= 400 else None


def read_snapshot(path: Path) -> dict | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_HISTORY_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def snapshot_entries(report: dict) -> list[dict]:
    """Pre-kickoff, unambiguous Cover projection with recorded price."""
    day_string = report.get("date_cdmx")
    try:
        day = date.fromisoformat(day_string)
    except (ValueError, TypeError):
        return []
    recorded = _parse_stamp(report.get("generated_at_utc"))
    if recorded is None or recorded.astimezone(LOCAL).date() != day:
        return []
    result = []
    for league in ("NBA", "NFL", "NHL"):
        section = report.get("leagues", {}).get(league, {})
        for event in section.get("events", []) if isinstance(section, dict) else []:
            if not isinstance(event, dict) or event.get("fecha_cdmx") != day_string:
                continue
            verified = event.get("espn")
            event_id = str(verified.get("evento") or "") if isinstance(verified, dict) else ""
            if not event_id.isdecimal() or not event.get("fuente_covers"):
                continue
            projections = event.get("proyeccion_covers")
            odds = event.get("momios_covers")
            if (not isinstance(projections, list) or len(projections) != 2 or
                    not isinstance(odds, list) or len(odds) != 2):
                continue
            try:
                kickoff = datetime.fromisoformat(
                    day_string + "T" + str(event["hora_cdmx"])
                ).replace(tzinfo=LOCAL)
            except (ValueError, TypeError, KeyError):
                continue
            if recorded >= kickoff.astimezone(timezone.utc):
                continue
            game = {
                "liga": league, "partido": event.get("partido", ""),
                "fecha_cdmx": day_string, "hora_cdmx": event.get("hora_cdmx"),
                "proyeccion_visitante": projections[0],
                "proyeccion_local": projections[1],
                "momio_visitante": odds[0], "momio_local": odds[1],
                "fuente": event["fuente_covers"],
            }
            reference = covers_projection(game, now=recorded)
            if not reference or not reference["momio_covers"]:
                continue
            price = reference["momio_covers"]
            if implied_percent(price) is None:
                continue
            entry_id = day_string + "|" + league + "|" + event_id
            result.append({
                "id": entry_id, "fecha": day_string, "liga": league,
                "partido": event["partido"], "evento_espn": event_id,
                "seleccion_covers": reference["seleccion_de_referencia"],
                "lado_proyectado": reference["lado_proyectado"],
                "momio_covers": price, "capturado_utc": recorded.isoformat(),
                "fuente_covers": event["fuente_covers"],
                "fuente_espn": verified.get("fuente") or "",
            })
    # Fail closed on duplicate event IDs within the same snapshot.
    by_id = {}
    for entry in result:
        by_id.setdefault(entry["id"], []).append(entry)
    return [items[0] for items in by_id.values() if len(items) == 1]


def grade_entry(entry: dict, game: dict) -> dict | None:
    if (game.get("event_id") != entry["evento_espn"]
            or game.get("sport") != entry["liga"]
            or str(game.get("local_date")) != entry["fecha"]
            or game.get("status") not in FINAL_STATES):
        return None
    away = _score(game.get("away_score"))
    home = _score(game.get("home_score"))
    if away is None or home is None or home == away:
        return None
    actual_side = "visitante" if away > home else "local"
    won = actual_side == entry["lado_proyectado"]
    odds = Decimal(str(entry["momio_covers"]))
    if odds == 0 or abs(odds) < 100:
        return None
    gross = (odds / Decimal(100) if odds > 0
             else Decimal(100) / abs(odds))
    pnl = (gross if won else Decimal("-1")).quantize(MONEY, rounding=ROUND_HALF_UP)
    return {
        **entry, "resultado": "ganado" if won else "perdido",
        "resultado_espn": f"{game['away']} {away} — {home} {game['home']}",
        "beneficio_unidad": str(pnl),
        "fuente_espn_resultado": game.get("source_url") or "",
        "calificado_utc": datetime.now(timezone.utc).isoformat(),
    }


def summarize(grades: dict[str, dict], *, asof: date) -> dict:
    decisions = [row for row in grades.values()
                 if row.get("resultado") in ("ganado", "perdido")]
    wins = sum(row["resultado"] == "ganado" for row in decisions)
    pnl = sum((Decimal(row["beneficio_unidad"]) for row in decisions), Decimal("0"))
    total = len(decisions)
    return {
        "fecha_cdmx": asof.isoformat(),
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "unidades_simuladas": total,
        "ganadas": wins, "perdidas": total - wins,
        "acierto_observado_pct": (round(100 * wins / total, 2) if total else None),
        "beneficio_unidades": str(pnl.quantize(MONEY)),
        "roi_observado_pct": (round(100 * float(pnl) / total, 2)
                             if total else None),
        "metodo": "Una unidad hipotetica por referencia Covers prepartido, "
                  "resuelta con resultado final ESPN. NO representa apuestas "
                  "realizadas ni probabilidades de modelo validado.",
        "grades": grades,
    }


def update_backtest(
    history_dir: Path, existing: dict | None = None, *, asof: date,
    board_fetch=fetch_scoreboard, max_requests: int = 10,
) -> dict:
    if not isinstance(max_requests, int) or not 1 <= max_requests <= 100:
        raise ValueError("Cantidad máxima de solicitudes inválida")
    grades = dict((existing or {}).get("grades") or {})
    # Validate previous grades rather than silently trusting unrelated JSON.
    grades = {
        key: value for key, value in grades.items()
        if isinstance(key, str) and isinstance(value, dict)
        and key == value.get("id")
        and value.get("resultado") in ("ganado", "perdido")
        and value.get("fuente_covers")
        and value.get("evento_espn")
    }
    pending_by_date = {}
    if history_dir.is_dir():
        for file in sorted(history_dir.glob("20??-??-??.json")):
            report = read_snapshot(file)
            if not report or report.get("date_cdmx") != file.stem:
                continue
            try:
                day = date.fromisoformat(file.stem)
            except ValueError:
                continue
            if day >= asof or (asof - day).days > 45:
                continue
            for entry in snapshot_entries(report):
                if entry["id"] not in grades:
                    pending_by_date.setdefault((day, entry["liga"]), []).append(entry)
    source_errors = []
    requests = 0
    for (day, league), entries in sorted(pending_by_date.items()):
        if requests >= max_requests:
            break
        requests += 1
        try:
            response = board_fetch(league, day)
            games = response.get("games", [])
        except (CalendarSourceError, ValueError, KeyError, OSError) as exc:
            source_errors.append(league + " " + day.isoformat() + ": " + str(exc))
            continue
        official = {}
        for game in games:
            if game.get("sport") == league and game.get("event_id"):
                official.setdefault(game["event_id"], []).append(game)
        for entry in entries:
            matches = official.get(entry["evento_espn"], [])
            if len(matches) != 1:
                continue
            outcome = grade_entry(entry, matches[0])
            if outcome is not None:
                grades[entry["id"]] = outcome
    result = summarize(grades, asof=asof)
    result["fuentes_con_error"] = source_errors
    result["pendientes_de_verificar"] = (
        sum(len(entries) for entries in pending_by_date.values())
        - sum(1 for entries in pending_by_date.values()
              for entry in entries if entry["id"] in grades)
    )
    result["consultas_espn"] = requests
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", default="data/history")
    parser.add_argument("--output", default="data/picks_backtest.json")
    parser.add_argument("--asof", default=None, help="YYYY-MM-DD en CDMX")
    args = parser.parse_args()
    today = date.fromisoformat(args.asof) if args.asof else datetime.now(LOCAL).date()
    output = Path(args.output)
    previous = read_snapshot(output)
    audit = update_backtest(Path(args.history_dir), previous, asof=today)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BACKTEST_COVERS", "aciertos", audit["ganadas"],
          "resueltos", audit["unidades_simuladas"],
          "pendientes", audit["pendientes_de_verificar"],
          "consultas", audit["consultas_espn"], flush=True)


if __name__ == "__main__":
    main()
