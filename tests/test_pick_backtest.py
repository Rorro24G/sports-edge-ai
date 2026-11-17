"""Audita referencias PRE-evento con resultados reales, sin fuga de información."""
import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import TestCase

from src.pick_backtest import (
    grade_entry, read_snapshot, snapshot_entries, summarize, update_backtest,
)


DAY = date(2026, 11, 16)


def snap(generated="2026-11-16T12:00:00+00:00", *, odds=None, event_id="4018"):
    return {
        "date_cdmx": DAY.isoformat(), "generated_at_utc": generated,
        "leagues": {
            "NBA": {"events": [{
                "liga": "NBA", "partido": "Toronto @ Boston",
                "fecha_cdmx": DAY.isoformat(), "hora_cdmx": "19:00",
                "fuente_covers": "https://www.covers.com/picks/nba",
                "proyeccion_covers": [109.5, 118.5],
                "momios_covers": odds if odds is not None else ["+160", "-145"],
                "espn": {"evento": event_id,
                         "fuente": "https://www.espn.com/nba/game/_/gameId/4018"},
            }]},
            "NFL": {"events": []}, "NHL": {"events": []},
        },
    }


def game(*, status="POST", away_score="103", home_score="119", event_id="4018"):
    return {
        "sport": "NBA", "event_id": event_id,
        "local_date": DAY, "status": status,
        "away_score": away_score, "home_score": home_score,
        "away": "Toronto Raptors", "home": "Boston Celtics",
        "source_url": "https://www.espn.com/nba/game/_/gameId/4018",
    }


class BacktestTests(TestCase):
    def test_precise_pre_kickoff_and_valid_odds(self):
        records = snapshot_entries(snap())
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["seleccion_covers"], "Boston ML")
        self.assertEqual(records[0]["lado_proyectado"], "local")
        self.assertEqual(records[0]["momio_covers"], "-145")
        self.assertEqual(records[0]["capturado_utc"],
                         "2026-11-16T12:00:00+00:00")
        # 19:00 CDMX is 01:00 UTC next day: this publication is too late.
        self.assertEqual(snapshot_entries(snap("2026-11-17T01:01:00+00:00")), [])
        self.assertEqual(snapshot_entries(snap(odds=["+160", None])), [])
        self.assertEqual(snapshot_entries(snap(odds=["+160", "52%"])), [])

    def test_no_doubtful_or_duplicate_source(self):
        source = snap()
        source["leagues"]["NBA"]["events"] *= 2
        self.assertEqual(snapshot_entries(source), [])
        source = snap(event_id="bad-id")
        self.assertEqual(snapshot_entries(source), [])

    def test_result_and_unit_profit_not_real_bank(self):
        entry = snapshot_entries(snap())[0]
        outcome = grade_entry(entry, game())
        self.assertEqual(outcome["resultado"], "ganado")
        self.assertEqual(outcome["beneficio_unidad"], "0.69")
        self.assertIn("Boston Celtics", outcome["resultado_espn"])
        loss = grade_entry(entry, game(away_score="122", home_score="119"))
        self.assertEqual(loss["resultado"], "perdido")
        self.assertEqual(loss["beneficio_unidad"], "-1.00")

    def test_final_event_identity_and_score_must_match(self):
        entry = snapshot_entries(snap())[0]
        for invalid in (
            game(status="IN"),
            game(event_id="99999"),
            game(home_score="103"),
            game(home_score="n/a"),
            dict(game(), local_date=date(2026, 11, 15)),
            dict(game(), sport="NHL"),
        ):
            with self.subTest(invalid=invalid):
                self.assertIsNone(grade_entry(entry, invalid))

    def test_grade_history_reuses_immutable_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "history"
            folder.mkdir()
            (folder / (DAY.isoformat() + ".json")).write_text(
                json.dumps(snap()), encoding="utf-8"
            )
            calls = []
            def board(league, day):
                calls.append((league, day))
                return {"games": [game()]}
            audit = update_backtest(folder, asof=date(2026, 11, 17),
                                    board_fetch=board)
            self.assertEqual(audit["ganadas"], 1)
            self.assertEqual(audit["unidades_simuladas"], 1)
            self.assertEqual(audit["acierto_observado_pct"], 100)
            self.assertEqual(audit["beneficio_unidades"], "0.69")
            self.assertEqual(audit["roi_observado_pct"], 69)
            self.assertEqual(len(calls), 1)
            again = update_backtest(folder, audit, asof=date(2026, 11, 18),
                                    board_fetch=board)
            self.assertEqual(again["unidades_simuladas"], 1)
            self.assertEqual(len(calls), 1)

    def test_no_betting_results_without_verified_espn(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / (DAY.isoformat() + ".json")).write_text(
                json.dumps(snap()), encoding="utf-8"
            )
            audit = update_backtest(
                folder, asof=date(2026, 11, 17),
                board_fetch=lambda *args: {"games": [game(status="IN")]}
            )
            self.assertIsNone(audit["acierto_observado_pct"])
            self.assertIsNone(audit["roi_observado_pct"])
            self.assertEqual(audit["pendientes_de_verificar"], 1)
            self.assertEqual(audit["unidades_simuladas"], 0)

    def test_prevent_future_archive_and_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "2026-11-16.json"
            path.write_text("{bad-json", encoding="utf-8")
            self.assertIsNone(read_snapshot(path))
            self.assertEqual(update_backtest(folder, asof=date(2026, 11, 17),
                                            board_fetch=lambda *x: 1)["consultas_espn"], 0)
            path.write_text(json.dumps(snap()), encoding="utf-8")
            self.assertEqual(update_backtest(folder, asof=DAY,
                                            board_fetch=lambda *x: 1)["consultas_espn"], 0)

    def test_summarize_no_validation_claim(self):
        data = summarize({}, asof=date(2026, 11, 17))
        self.assertEqual(data["unidades_simuladas"], 0)
        self.assertIsNone(data["acierto_observado_pct"])
        self.assertIn("NO representa apuestas", data["metodo"])
