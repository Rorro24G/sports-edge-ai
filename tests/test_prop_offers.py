"""Los props sólo muestran momios con identidad y vigencia verificadas."""
from datetime import date, datetime, timezone, timedelta
from unittest import TestCase
from unittest.mock import patch

from src.prop_offers import (
    _american, select_single_event, extract_exact_prop_offers,
    fetch_player_prop_offers,
)
from src.prop_review import matching_player_game, player_prop_review
from src.player_props import PlayerQuestion

NOW = datetime(2026, 11, 17, 17, 0, tzinfo=timezone.utc)
DAY = date(2026, 11, 17)
GAME = {
    "sport": "NBA", "away": "Golden State Warriors",
    "home": "Los Angeles Lakers", "away_team_id": "9",
    "home_team_id": "13", "local_date": DAY,
    "local_time": "22:00", "status": "SCHEDULED",
}
EVENT = {
    "id": "abcdef0123456789", "away_team": "Golden State Warriors",
    "home_team": "Los Angeles Lakers",
    "commence_time": "2026-11-18T04:00:00Z",
}
QUOTE = {
    **EVENT,
    "bookmakers": [
        {"title": "BetMGM", "markets": [{
            "key": "player_points", "last_update": "2026-11-17T16:50:00Z",
            "outcomes": [
                {"name": "Over", "description": "Luka Doncic",
                 "point": 24.5, "price": -110},
                {"name": "Under", "description": "Luka Doncic",
                 "point": 24.5, "price": -110},
                {"name": "Over", "description": "Other Player",
                 "point": 24.5, "price": +155},
                {"name": "Over", "description": "Luka Doncic",
                 "point": 25.5, "price": +145},
            ],
        }]},
        {"title": "Another Sportsbook", "markets": [{
            "key": "player_rebounds", "last_update": "2026-11-17T16:50:00Z",
            "outcomes": [{"name": "Over", "description": "Luka Doncic",
                          "point": 24.5, "price": +145}],
        }]},
    ],
}
PLAYER = {"id": "3945274", "name": "Luka Doncic", "team_id": "13",
          "injuries": [{"status": "Questionable"}], "status": "Questionable"}
HISTORY = [{"date": f"2026-11-{i:02d}", "value": 20 + i}
           for i in range(16, 6, -1)]


class PropMarketTests(TestCase):
    def test_only_one_identical_nba_event(self):
        self.assertEqual(select_single_event([EVENT], GAME, DAY, now=NOW)["id"], EVENT["id"])
        self.assertIsNone(select_single_event([EVENT, EVENT], GAME, DAY, now=NOW))
        self.assertIsNone(select_single_event([
            dict(EVENT, home_team="Los Angeles Clippers")
        ], GAME, DAY, now=NOW))
        self.assertIsNone(select_single_event([
            dict(EVENT, commence_time="2026-11-18T03:00:00Z")
        ], GAME, DAY, now=NOW))

    def test_only_matching_player_market_direction_and_line(self):
        rows = extract_exact_prop_offers(QUOTE, player_name="Luka Doncic",
                                         stat="PTS", direction="over", line=24.5, now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["casa"], "BetMGM")
        self.assertEqual(rows[0]["momio_americano"], -110)
        self.assertEqual(rows[0]["linea"], "24.5")
        self.assertEqual(rows[0]["actualizado_utc"], "2026-11-17T16:50:00+00:00")
        self.assertEqual(rows[0]["fuente"], "The Odds API")
        self.assertEqual(extract_exact_prop_offers(
            QUOTE, player_name="Luka Doncic", stat="REB", direction="under",
            line=24.5, now=NOW), [])

    def test_old_market_data_and_percentages_are_rejected(self):
        self.assertEqual(_american("55%"), None)
        self.assertEqual(_american(55), None)
        self.assertEqual(_american(-110.5), None)
        stale = {**QUOTE, "bookmakers": [
            {"title": "Test", "markets": [{
                "key": "player_points", "last_update": "2026-11-17T13:00:00Z",
                "outcomes": [{"name": "Over", "description": "Luka Doncic",
                              "point": 24.5, "price": -115}],
            }]}
        ]}
        self.assertEqual(extract_exact_prop_offers(
            stale, player_name="Luka Doncic", stat="PTS", direction="over",
            line=24.5, now=NOW), [])

    def test_no_api_calls_without_a_key(self):
        with patch("src.prop_offers._fetch") as fetch:
            self.assertEqual(fetch_player_prop_offers(
                "", game=GAME, target=DAY, player_name="Luka Doncic",
                stat="PTS", direction="over", line=24.5), [])
            fetch.assert_not_called()

    def test_review_includes_injury_small_sample_no_proven_ev(self):
        game = matching_player_game(PLAYER, [GAME], DAY)
        self.assertIsNotNone(game)
        question = PlayerQuestion("PTS", "over", 24.5)
        report = player_prop_review(PLAYER, HISTORY[:4], question, game=game)
        self.assertTrue(any("lesión" in x for x in report["risk_flags"]))
        self.assertTrue(any("Muestra" in x for x in report["risk_flags"]))
        self.assertTrue(any("Sin cotización" in x for x in report["risk_flags"]))
        self.assertIsNone(report["model_probability"])
        self.assertIsNone(report["expected_value"])
        self.assertIsNone(report["recommendation"])

    def test_player_team_must_match_one_and_only_one_game(self):
        self.assertIsNone(matching_player_game(PLAYER, [GAME, GAME], DAY))
        self.assertIsNone(matching_player_game(
            dict(PLAYER, team_id="99"), [GAME], DAY))
        self.assertIsNone(matching_player_game(PLAYER, [
            dict(GAME, local_date=date(2026, 11, 18))], DAY))


    def test_started_or_unconfirmed_start_never_returns_quotes(self):
        for start in (None, "invalid", "2026-11-17T17:00:00Z", "2026-11-17T16:59:00Z"):
            with self.subTest(start=start):
                self.assertEqual(extract_exact_prop_offers(
                    dict(QUOTE, commence_time=start), player_name="Luka Doncic",
                    stat="PTS", direction="over", line=24.5, now=NOW), [])

    def test_quote_preserves_event_and_capture_time(self):
        quote = extract_exact_prop_offers(
            QUOTE, player_name="Luka Doncic", stat="PTS", direction="over",
            line=24.5, now=NOW)[0]
        self.assertEqual(quote["evento_proveedor"], EVENT["id"])
        self.assertEqual(quote["consultado_utc"], NOW.isoformat())
        self.assertEqual(quote["inicio_utc"], "2026-11-18T04:00:00+00:00")

    def test_missing_team_id_cannot_match_missing_game_team_id(self):
        self.assertIsNone(matching_player_game(
            dict(PLAYER, team_id=""), [dict(GAME, home_team_id="")], DAY))

    def test_no_injury_report_does_not_confirm_availability(self):
        review = player_prop_review(
            dict(PLAYER, injuries=[], status="Active"), HISTORY,
            PlayerQuestion("PTS", "over", 24.5), game=GAME,
        )
        self.assertTrue(any("no confirma disponibilidad" in x for x in review["risk_flags"]))
