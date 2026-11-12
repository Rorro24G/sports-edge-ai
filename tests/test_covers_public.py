"""Pruebas del lector de Covers: fecha, cuotas observadas y ausencia de datos falsos."""
from datetime import date
from unittest import TestCase
from unittest.mock import patch
import io

from src.covers_public import parse_public_picks, fetch_public_picks, CoversSourceError


PUBLIC_HTML = """
<html><body>
<h1>NBA Picks</h1><p>Free NBA Expert and Computer Picks For Every Game Nov. 12, 2026</p>
<div>Toronto @ Philadelphia</div>
<div>Today • 7:00 PM ET</div>
<p>Computer Picks</p><p>Predicted Score</p>
<div>TOR TOR</div><div>107.63 @ ⯆ 116.12</div><div>PHI PHI</div>
<p>Raptors vs 76ers · Prediction & Game Odds</p>
<div>Team Predicted Score Spread Total ML</div>
<div>TOR TOR 107.63 +8.5 -110 o223.5 -111 +265</div>
<div>PHI PHI 116.12 -8.5 -105 u224.5 -110 -330</div>
<div>Detroit @ Washington</div><div>Nov 13 • 7:00 PM ET</div>
<div>Computer Picks</div><div>Predicted Score</div>
<div>DET 111.25 @ 109.25 WAS</div>
</body></html>
"""


class PublicCoversTests(TestCase):
    def test_parse_only_requested_mexico_day(self):
        result = parse_public_picks(PUBLIC_HTML, "NBA", date(2026, 11, 12))
        self.assertEqual(result["page_date"], "2026-11-12")
        self.assertEqual(len(result["events"]), 1)
        game = result["events"][0]
        self.assertEqual(game["partido"], "Toronto @ Philadelphia")
        self.assertEqual(game["hora_cdmx"], "18:00")
        self.assertEqual(game["proyeccion_visitante"], 107.63)
        self.assertEqual(game["proyeccion_local"], 116.12)
        self.assertIn("o223.5 -111", game["totales_publicados"])
        self.assertIn("+8.5 -110", game["spreads_publicados"])
        self.assertIsNone(game["probabilidades_publicadas"])

    def test_no_old_data_for_arbitrary_future_day(self):
        result = parse_public_picks(PUBLIC_HTML, "NBA", date(2026, 11, 18))
        self.assertEqual(result["events"], [])

    def test_bad_page_fails_clearly(self):
        with self.assertRaises(CoversSourceError):
            parse_public_picks("<html>Login required</html>", "NBA", date(2026, 11, 12))

    def test_forbidden_access_not_bypassed(self):
        from urllib.error import HTTPError
        with patch("src.covers_public.urlopen", side_effect=HTTPError("https://www.covers.com/picks/nba", 403, "Forbidden", {}, io.BytesIO())):
            with self.assertRaisesRegex(CoversSourceError, "HTTP 403"):
                fetch_public_picks("NBA", date(2026, 11, 12))

    def test_reject_unknown_sport(self):
        with self.assertRaises(ValueError):
            parse_public_picks(PUBLIC_HTML, "ATP", date(2026, 11, 12))
