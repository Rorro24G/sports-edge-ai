"""Tests sin red: fecha México, normalización y momios reales sin fabricaciones."""
from __future__ import annotations
from datetime import date
from unittest import TestCase
from unittest.mock import patch
from src.live_board import scoreboard_url, normalize_scoreboard
from src.live_odds import odds_for_day


class LiveBoardTests(TestCase):
    def test_url_changes_per_day(self):
        self.assertIn("dates=20261112", scoreboard_url("NBA", date(2026,11,12)))
        self.assertIn("hockey/nhl", scoreboard_url("NHL", date(2026,11,12)))

    def test_mexico_time_and_no_invented_odds(self):
        fixture = {"events": [{
            "id": "ESPN_123",
            "date": "2026-11-13T02:30Z",
            "status": {"type": {"state": "pre"}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "team": {"displayName": "Home Team"}},
                {"homeAway": "away", "team": {"displayName": "Away Team"}},
            ]}],
            "links": [{"href": "https://www.espn.com/game/_/id/123"}],
        }]}
        rows = normalize_scoreboard(fixture,"NBA",date(2026,11,12))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["local_time"],"20:30")
        self.assertEqual(rows[0]["market_status"],"SIN_CUOTAS_VERIFICADAS")
        self.assertEqual(rows[0]["prediction_status"],"SIN_MODELO_VALIDADO")

    def test_mismatched_date_is_filtered(self):
        fixture = {"events":[{"id":"x","date":"2026-11-13T02:30Z",
            "competitions":[{"competitors":[
                {"homeAway":"home","team":{"displayName":"A"}},
                {"homeAway":"away","team":{"displayName":"B"}}]}]}]}
        self.assertEqual(normalize_scoreboard(fixture,"NBA",date(2026,11,13)),[])


class LiveOddsTests(TestCase):
    def test_no_key_calls_no_api(self):
        with patch("src.live_odds._fetch") as fetch:
            self.assertEqual(odds_for_day("",("NBA",),date(2026,11,12)),[])
            fetch.assert_not_called()

    def test_three_markets_and_source_metadata(self):
        event={"commence_time":"2030-11-13T02:00:00Z","away_team":"Away",
            "home_team":"Home","bookmakers":[{"title":"Test Sportsbook",
            "markets":[
                {"key":"h2h","last_update":"2030-11-12T02:00:00Z","outcomes":[{"name":"Home","price":-110}]},
                {"key":"spreads","outcomes":[{"name":"Home","point":-4.5,"price":-105}]},
                {"key":"totals","outcomes":[{"name":"Over","point":225.5,"price":-115}]}]}]}
        with patch("src.live_odds._fetch",return_value=[event]):
            result=odds_for_day("fake-test-only",("NBA",),date(2030,11,12))
        self.assertEqual(len(result),3)
        self.assertEqual({x["market"] for x in result},{"h2h","spreads","totals"})
        self.assertTrue(all(x["source"]=="The Odds API" for x in result))
