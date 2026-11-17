"""Pruebas del contexto por encuentro: sin mezclar rivales ni fingir lesiones."""
from unittest import TestCase
from unittest.mock import patch

from src.pick_context import (match_espn_event, parse_summary,
                              summary_url, fetch_summary, ContextSourceError)


class PickContextTests(TestCase):
    def test_match_both_sides(self):
        covers = {"liga": "NBA", "partido": "Toronto @ Philadelphia", "hora_cdmx": "18:00"}
        games = [
            {"sport": "NBA", "away": "Detroit Pistons",
             "home": "Philadelphia 76ers", "event_id": "11111",
             "local_time": "18:00"},
            {"sport": "NBA", "away": "Toronto Raptors",
             "home": "Philadelphia 76ers", "event_id": "22222",
             "local_time": "18:00"},
        ]
        self.assertEqual(match_espn_event(covers, games)["event_id"], "22222")

    def test_ny_alias_and_wrong_league(self):
        covers = {"liga": "NFL", "partido": "Washington @ N.Y. Giants"}
        games = [
            {"sport": "NBA", "away": "Washington Wizards",
             "home": "New York Knicks", "event_id": "12345"},
            {"sport": "NFL", "away": "Washington Commanders",
             "home": "New York Giants", "event_id": "98765"},
        ]
        self.assertEqual(match_espn_event(covers, games)["event_id"], "98765")

    def test_unmatched_and_ambiguous_return_none(self):
        covers = {"liga": "NHL", "partido": "Montreal @ Boston"}
        bad = [{"sport": "NHL", "away": "Boston Bruins",
                "home": "Montreal Canadiens", "event_id": "11111"}]
        self.assertIsNone(match_espn_event(covers, bad))
        same = {"sport": "NHL", "away": "Montreal Canadiens",
                "home": "Boston Bruins", "event_id": "22222"}
        self.assertIsNone(match_espn_event(covers, [same, dict(same)]))

    def test_extract_injuries_and_leaders(self):
        sample = {
            "injuries": [{"team": {"displayName": "Toronto Raptors"},
                          "injuries": [
                              {"athlete": {"displayName": "Jugador A"},
                               "status": "Questionable",
                               "type": {"description": "Knee"}},
                              {"athlete": {"displayName": "Jugador B"},
                               "status": "Out"}]}],
            "leaders": [{"team": {"displayName": "Philadelphia 76ers"},
                         "leaders": [{"displayName": "Points",
                                      "leaders": [{"athlete": {"displayName": "Jugador C"},
                                                   "displayValue": "27.0 PPG"}]}]}],
            "gameInfo": {"venue": {"fullName": "Example Arena"}},
        }
        result = parse_summary(sample, url="https://example.com/summary")
        self.assertEqual(result["injuries"][0]["Estado ESPN"], "Questionable")
        self.assertEqual(result["injuries"][1]["Motivo"], "No indicado")
        self.assertEqual(result["leaders"][0]["Jugador"], "Jugador C")
        self.assertEqual(result["venue"], "Example Arena")

    def test_missing_report_does_not_equal_healthy(self):
        result = parse_summary({}, url="https://example.com/summary")
        self.assertEqual(result["injuries"], [])
        self.assertEqual(result["leaders"], [])

    def test_id_restricted_and_summary_url(self):
        self.assertIn("football/nfl/summary?event=401123456",
                      summary_url("NFL", "401123456"))
        with self.assertRaises(ValueError):
            summary_url("NFL", "https://other.domain/")
        with self.assertRaises(ValueError):
            summary_url("ATP", "401123456")

    def test_network_failure_is_reported_not_faked(self):
        from urllib.error import HTTPError
        with patch("src.pick_context.urlopen", side_effect=HTTPError(
                "https://example.com/", 403, "Forbidden", {}, None)):
            with self.assertRaisesRegex(ContextSourceError, "HTTP 403"):
                fetch_summary("NBA", "401123456")

    def test_news_from_espn_summary_only(self):
        payload = {"news": {"articles": [
            {"headline": "Actualizacion de la plantilla", "links": {"web": {"href": "https://www.espn.com/nba/story/_/id/123/roster"}}},
            {"headline": "URL no permitida", "links": {"web": {"href": "https://example.org/not-real"}}},
            {"headline": "Duplicada", "links": {"web": {"href": "https://www.espn.com/nba/story/_/id/123/roster"}}},
            {"headline": "No reportar sin fuente"},
        ]}}
        result = parse_summary(payload, url="https://site.api.espn.com/summary")
        self.assertEqual(len(result["news"]), 1)
        self.assertEqual(result["news"][0]["Titular ESPN"], "Actualizacion de la plantilla")

    def test_no_news_when_missing(self):
        self.assertEqual(parse_summary({}, url="https://espn.com/")["news"], [])
