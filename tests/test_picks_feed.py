"""No fake Covers odds, no lost ESPN games, no stale dates."""
from datetime import date
from unittest import TestCase
from unittest.mock import patch

from src.picks_feed import live_picks_catalog, pick_catalog_rows


DAY = date(2026, 11, 17)
COVERS = {
    "liga": "NHL", "partido": "Montreal @ Boston",
    "fecha_cdmx": "2026-11-17", "hora_cdmx": "18:00",
    "fuente": "https://www.covers.com/picks/nhl",
    "proyeccion_visitante": 2.9, "proyeccion_local": 3.5,
    "momio_visitante": "+140", "momio_local": "-165",
}
ESPN = {
    "sport": "NHL", "away": "Montreal Canadiens", "home": "Boston Bruins",
    "local_time": "18:00", "status": "SCHEDULED", "event_id": "401",
    "source_url": "https://www.espn.com/nhl/game/_/gameId/401",
}
OTHER = {
    "sport": "NHL", "away": "Seattle Kraken", "home": "San Jose Sharks",
    "local_time": "19:00", "status": "SCHEDULED", "event_id": "402",
    "source_url": "https://www.espn.com/nhl/game/_/gameId/402",
}


class PicksFeedTests(TestCase):
    def test_covers_pricing_and_espn_fallback(self):
        rows = live_picks_catalog([COVERS], {"NHL": [ESPN, OTHER]}, DAY)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["origen"], "Covers")
        self.assertEqual(rows[0]["momio_visitante"], "+140")
        self.assertEqual(rows[1]["origen"], "ESPN")
        self.assertIsNone(rows[1]["momio_visitante"])
        table = pick_catalog_rows(rows)
        self.assertEqual(table[0]["ML local"], "-165")
        self.assertEqual(table[1]["ML local"], "—")

    def test_reject_wrong_day_from_covers(self):
        stale = dict(COVERS, fecha_cdmx="2026-11-16")
        rows = live_picks_catalog([stale], {"NHL": [ESPN]}, DAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["origen"], "ESPN")

    def test_preserve_real_covers_even_when_espn_unavailable(self):
        rows = live_picks_catalog([COVERS], {"NHL": []}, DAY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["momio_local"], "-165")
