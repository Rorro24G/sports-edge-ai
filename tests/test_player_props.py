"""Tests sin red: búsqueda de jugador NBA y últimos partidos verificables."""
from datetime import date
from unittest import TestCase

from src.player_props import (
    gamelog_url, parse_gamelog, parse_player_question,
    parse_roster, resolve_player, resolve_player_in_games,
    roster_url, season_for, summarize_prop,
)

TODAY = date(2026, 11, 17)


def fake_gamelog():
    return {
        "labels": ["MIN", "FG", "3PT", "FT", "REB", "AST", "PTS"],
        "events": {
            "101": {"gameDate": "2026-11-12T02:00Z", "opponent": {"abbreviation": "BOS"}},
            "102": {"gameDate": "2026-11-14T02:00Z", "opponent": {"abbreviation": "NYK"}},
            "103": {"gameDate": "2026-11-18T02:00Z", "opponent": {"abbreviation": "CHI"}},
            "104": {"gameDate": "2026-11-10T02:00Z", "opponent": {"abbreviation": "TOR"}},
        },
        "seasonTypes": [
            {"id": "2", "displayName": "2026-27 Regular Season", "categories": [
                {"events": [
                    {"eventId": "101", "stats": ["34", "10-20", "3-9", "3-4", "6", "7", "29"]},
                    {"eventId": "102", "stats": ["36", "12-24", "4-10", "4-4", "5", "8", "32"]},
                    {"eventId": "103", "stats": ["32", "10-20", "2-8", "3-4", "5", "8", "25"]},
                    {"eventId": "104", "stats": ["DNP", "DNP", "DNP", "DNP", "DNP", "DNP", "DNP"]},
                ]},
                {"events": [{"eventId": "102", "stats": ["36", "12-24", "4-10",
                                                       "4-4", "5", "8", "32"]}]},
            ]},
            {"id": "1", "displayName": "Preseason", "categories": [
                {"events": [{"eventId": "101", "stats": ["34", "10-20", "3-9",
                                                       "3-4", "6", "7", "99"]}]}
            ]},
        ],
    }


class PlayerPropsTests(TestCase):
    def test_spanish_and_english_questions(self):
        cases = [
            ("Over de 24,5 puntos de Luka Doncic NBA", "PTS", "over", 24.5),
            ("más de 8.5 rebotes de Luka", "REB", "over", 8.5),
            ("under de 6,5 asistencias de Doncic", "AST", "under", 6.5),
            ("4.5 triples de Curry", "3PM", None, 4.5),
            ("puntos de Luka", "PTS", None, None),
        ]
        for text, stat, direction, line in cases:
            with self.subTest(text=text):
                actual = parse_player_question(text)
                self.assertIsNotNone(actual)
                self.assertEqual((actual.stat, actual.direction, actual.line),
                                 (stat, direction, line))
        self.assertIsNone(parse_player_question("Lakers contra Boston moneyline"))

    def test_unique_full_name_and_surname(self):
        players = [
            {"id": "1", "name": "Luka Doncic"},
            {"id": "2", "name": "LeBron James"},
            {"id": "3", "name": "James Harden"},
        ]
        self.assertEqual(resolve_player("Over puntos de Luka Doncic", players)["id"], "1")
        self.assertEqual(resolve_player("Over puntos de Doncic", players)["id"], "1")
        self.assertIsNone(resolve_player("Under asistencias James", players))
        self.assertIsNone(resolve_player("puntos de Alexander", players))

    def test_rosters_flat_or_grouped(self):
        payload = {"athletes": [
            {"id": "1966", "displayName": "LeBron James",
             "status": {"name": "Active"}, "injuries": []},
            {"items": [{"id": "3945274", "fullName": "Luka Doncic"}]},
        ]}
        got = parse_roster(payload, "13")
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["status"], "Active")
        self.assertEqual(got[1]["name"], "Luka Doncic")
        self.assertIn("/teams/13/roster", roster_url("13"))
        with self.assertRaises(ValueError):
            roster_url("../../13")
        with self.assertRaises(ValueError):
            gamelog_url("oops", 2027)

    def test_search_only_current_team_rosters(self):
        games = [
            {"sport": "NBA", "away_team_id": "13", "home_team_id": "9"},
            {"sport": "NBA", "away_team_id": "13", "home_team_id": "9"},
            {"sport": "NHL", "away_team_id": "23", "home_team_id": "4"},
        ]
        called = []
        def fake_roster(team):
            called.append(team)
            return {"athletes": ([{"id": "3945274", "name": "Luka Doncic"}]
                                 if team == "13" else [])}
        person = resolve_player_in_games("Over 24.5 puntos de Luka Doncic", games,
                                         roster_fetch=fake_roster)
        self.assertEqual(person["id"], "3945274")
        self.assertCountEqual(called, ["13", "9"])

    def test_only_prior_regular_season_no_dupes(self):
        log = fake_gamelog()
        pts = parse_gamelog(log, "PTS", TODAY)
        self.assertEqual([r["value"] for r in pts], [32, 29])
        self.assertEqual([r["opponent"] for r in pts], ["NYK", "BOS"])
        self.assertEqual([r["value"] for r in parse_gamelog(log, "3PM", TODAY)], [4, 3])
        self.assertEqual([r["value"] for r in parse_gamelog(log, "REB", TODAY)], [5, 6])

    def test_historical_hit_rate_not_predicted_probability(self):
        request = parse_player_question("Over de 30.5 puntos Luka Doncic NBA")
        rows = parse_gamelog(fake_gamelog(), "PTS", TODAY)
        data = summarize_prop(rows, request)
        self.assertEqual(data["games"], 2)
        self.assertEqual(data["last5"], 30.5)
        self.assertEqual(data["historical_hits"], 1)
        self.assertEqual(data["historical_sample"], 2)
        self.assertEqual(data["historical_rate"], 50.0)
        self.assertEqual(data["pushes"], 0)

    def test_requires_explicit_line_for_hits(self):
        question = parse_player_question("puntos de Luka Doncic")
        stats = summarize_prop(parse_gamelog(fake_gamelog(), "PTS", TODAY), question)
        self.assertIsNone(stats["historical_rate"])
        self.assertEqual(stats["games"], 2)
        self.assertEqual(summarize_prop([], question)["games"], 0)

    def test_season_date(self):
        self.assertEqual(season_for(date(2026, 11, 17)), 2027)
        self.assertEqual(season_for(date(2027, 5, 17)), 2027)
