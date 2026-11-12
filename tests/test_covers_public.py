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
        self.assertEqual(game["momio_visitante"], "+265")
        self.assertEqual(game["momio_local"], "-330")
        self.assertIn("o223.5 -111", game["totales_publicados"])
        self.assertIn("+8.5 -110", game["spreads_publicados"])
        self.assertIsNone(game["probabilidades_publicadas"])

    def test_incomplete_moneyline_is_not_guessed(self):
        html = PUBLIC_HTML.replace(
            "TOR TOR 107.63 +8.5 -110 o223.5 -111 +265",
            "TOR TOR 107.63 +8.5 -110 o223.5 -111")
        result = parse_public_picks(html, "NBA", date(2026, 11, 12))
        self.assertIsNone(result["events"][0]["momio_visitante"])
        self.assertIsNone(result["events"][0]["momio_local"])

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

    def test_nhl_percentages_are_not_american_odds(self):
        html = """
        <h1>NHL Picks</h1>
        <div>Free NHL Expert and Computer Picks For Every Game Nov. 12, 2026</div>
        <div>Montreal @ Boston</div>
        <div>Today • 7:00 PM ET</div>
        <p>Computer Picks</p><p>Predicted Score</p>
        <div>MON MON</div><div>2.92 @ ⯆ 3.25</div><div>BOS BOS</div>
        <div>Canadiens vs Bruins · Prediction & Game Odds</div>
        <div>Team Predicted Score ML Total Puck Line</div>
        <div>MON MON 2.92 46% o6.0 53% +1.5 68%</div>
        <div>BOS BOS 3.25 54% u6.5 55% -1.5 33%</div>
        """
        parsed = parse_public_picks(html, "NHL", date(2026, 11, 12))
        self.assertEqual(len(parsed["events"]), 1)
        game = parsed["events"][0]
        self.assertEqual(game["proyeccion_visitante"], 2.92)
        self.assertEqual(game["proyeccion_local"], 3.25)
        self.assertIn("o6.0 53%", game["totales_publicados"])
        self.assertIn("u6.5 55%", game["totales_publicados"])
        self.assertIn("+1.5 68%", game["spreads_publicados"])
        self.assertEqual(game["tipo_mercados"], "proyecciones_porcentuales")

    def test_nfl_probabilities_with_local_start(self):
        html = """
        <h1>Best NFL Picks Today</h1>
        <p>Find the best NFL bets today - Nov. 12, 2026. Free expert and computer picks.</p>
        <div>Washington @ N.Y. Giants</div>
        <div>Today • 8:15 PM ET</div>
        <div>Computer Picks</div><div>Predicted Score</div>
        <div>WAS WAS</div><div>20.47 @ 18.43</div><div>NYG NYG</div>
        <div>Commanders vs Giants · Prediction & Game Odds</div>
        <div>Team Predicted Score Spread Total ML</div>
        <div>WAS WAS 20.47 +2.5 54% o40.5 53% 45%</div>
        <div>NYG NYG 18.43 -2.5 51% u41.5 53% 55%</div>
        """
        parsed = parse_public_picks(html, "NFL", date(2026, 11, 12))
        self.assertEqual(len(parsed["events"]), 1)
        game = parsed["events"][0]
        self.assertEqual(game["hora_cdmx"], "19:15")
        self.assertIn("o40.5 53%", game["totales_publicados"])
        self.assertIn("+2.5 54%", game["spreads_publicados"])
        self.assertIn("45%", game["probabilidades_publicadas"])
        self.assertEqual(game["tipo_mercados"], "proyecciones_porcentuales")
