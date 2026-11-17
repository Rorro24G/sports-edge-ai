"""Tests de portada matutina. Jamás tratar una copia antigua como hoy."""
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import TestCase
from zoneinfo import ZoneInfo

from src.brain_dashboard import load_today_snapshot, morning_rows

LOCAL = ZoneInfo("America/Mexico_City")


def fixture(day, *, generated=None):
    return {
        "date_cdmx": day.isoformat(),
        "generated_at_utc": (generated or datetime.now(timezone.utc)).isoformat(),
        "leagues": {
            "NBA": {"coverage": {}, "errors": [], "events": [
                {"liga": "NBA", "partido": "Toronto @ Boston",
                 "fecha_cdmx": day.isoformat(), "hora_cdmx": "18:00",
                 "momios_covers": ["+135", "-155"], "espn": {"evento": "123"}}]},
            "NFL": {"coverage": {}, "errors": [], "events": []},
            "NHL": {"coverage": {}, "errors": [], "events": []},
        },
    }


class BriefingTests(TestCase):
    def test_exact_date_only(self):
        today = datetime.now(LOCAL).date()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "brief.json"
            report = fixture(today)
            dest.write_text(json.dumps(report), encoding="utf-8")
            self.assertIsNotNone(load_today_snapshot(today, dest))
            self.assertIsNone(load_today_snapshot(today - timedelta(days=1), dest))
            self.assertIsNone(load_today_snapshot(today + timedelta(days=1), dest))

    def test_future_generation_rejected(self):
        today = datetime.now(LOCAL).date()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "brief.json"
            report = fixture(today, generated=datetime.now(timezone.utc) + timedelta(hours=2))
            dest.write_text(json.dumps(report), encoding="utf-8")
            self.assertIsNone(load_today_snapshot(today, dest))

    def test_bad_json_never_displays_old_market(self):
        today = datetime.now(LOCAL).date()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "brief.json"
            dest.write_text("{invalid", encoding="utf-8")
            self.assertIsNone(load_today_snapshot(today, dest))

    def test_rows_show_external_prices_and_no_invented_prediction(self):
        today = datetime.now(LOCAL).date()
        rows = morning_rows(fixture(today))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Liga"], "NBA")
        self.assertEqual(rows[0]["Moneyline"], "+135 / -155 · Covers")
        self.assertEqual(rows[0]["Pick propio"], "Sin modelo validado")

    def test_only_same_date_events(self):
        today = datetime.now(LOCAL).date()
        report = fixture(today)
        report["leagues"]["NBA"]["events"][0]["fecha_cdmx"] = (
            today - timedelta(days=1)).isoformat()
        self.assertEqual(morning_rows(report), [])
