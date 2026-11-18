"""Run an optional ESPN-only chronological audit of the SEAI judgement model.

Example (with network): python scripts/backtest_seai.py --sport NBA
    --start 2026-10-26 --end 2026-11-16 --max-games 35

A real audit requires ESPN connectivity. In an outage this command exits with
an explicit error rather than fabricating results. The unit tests are offline.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from datetime import date, timedelta
from pathlib import Path

from src.live_board import CalendarSourceError, fetch_scoreboard
from src.pick_walkforward import walkforward
from src.team_form import TeamFormError, fetch_team_schedule, season_year


def run(sport: str, start: date, end: date, *, max_games: int = 40) -> dict:
    if sport not in ("NBA", "NFL", "NHL"):
        raise ValueError("Liga no soportada")
    if end < start or (end-start).days > 60 or not 1 <= max_games <= 240:
        raise ValueError("Fechas fuera de rango (máximo 61 días y 240 partidos)")
    if season_year(sport, start) != season_year(sport, end):
        raise ValueError("El backtest debe permanecer en una sola temporada")
    fixtures, error_dates = [], []
    day = start
    while day <= end and len(fixtures) < max_games:
        try:
            board = fetch_scoreboard(sport, day)
        except CalendarSourceError:
            error_dates.append(day.isoformat())
            day += timedelta(days=1)
            continue
        fixtures.extend(g for g in board.get("games", []) if g.get("status") == "POST")
        day += timedelta(days=1)
    fixtures = fixtures[:max_games]
    ids = {(sport, str(g["away_team_id"])) for g in fixtures}
    ids |= {(sport, str(g["home_team_id"])) for g in fixtures}
    histories, history_failures = {}, []
    # Request full ESPN season through audit end (at most one per team).
    # Future completed results remain in histories but _history() filters
    # strictly by EACH fixture's date before extracting model features.
    with ThreadPoolExecutor(max_workers=5) as executor:
        jobs = {
            executor.submit(fetch_team_schedule, league, team_id,
                            end + timedelta(days=1)): (league, team_id)
            for league, team_id in sorted(ids)
        }
        for future in as_completed(jobs):
            league, team_id = jobs[future]
            try:
                histories[(league, team_id)] = future.result()
            except (TeamFormError, ValueError, OSError):
                history_failures.append(f"{league}:{team_id}")
    report = walkforward(fixtures, histories)
    report["sport"] = sport
    report["period"] = {"start": start.isoformat(), "end": end.isoformat()}
    report["source"] = "ESPN scoreboard + ESPN team schedules"
    report["audited_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["scoreboard_errors"] = error_dates
    report["team_history_failures"] = sorted(history_failures)
    report["retrieved_fixture_count"] = len(fixtures)
    report["retrieved_team_count"] = len(histories)
    report["data_complete"] = not error_dates and not history_failures
    report["source_note"] = (
        "Solo ESPN. Cada predicción se produce con resultados anteriores "
        "al encuentro. No se atribuyen cuotas históricas ni ganancias."
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", choices=["NBA", "NFL", "NHL"], default="NBA")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--max-games", type=int, default=40)
    parser.add_argument("--output", type=Path, default=Path("daily-output/own-model-audit.json"))
    args = parser.parse_args()
    report = run(args.sport, args.start, args.end, max_games=args.max_games)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {k: v for k, v in report.items() if k not in {"details"}}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if report["evaluated_count"] == 0:
        print("No hubo encuentros históricos evaluables con los datos recibidos", file=sys.stderr)
        sys.exit(2)
    if not report["data_complete"]:
        print("ADVERTENCIA: auditoría parcial por fallos de proveedores; "
              "no interpretar los promedios como cobertura completa.", file=sys.stderr)


if __name__ == "__main__":
    main()
