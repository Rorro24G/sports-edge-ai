"""Pruebas de elección por partido, sin modificar las simulaciones."""
from unittest import TestCase
from src.match_report import rank_matches


GAMES = [
    {"liga": "NBA", "partido": "Detroit @ Washington"},
    {"liga": "NHL", "partido": "Montreal @ Boston"},
    {"liga": "NBA", "partido": "Toronto @ Philadelphia"},
]


class MatchReportTests(TestCase):
    def test_prioritizes_named_match(self):
        found = rank_matches(GAMES, "Analiza Toronto contra Philadelphia hoy")
        self.assertEqual(found[0]["partido"], "Toronto @ Philadelphia")
        self.assertEqual(len(found), 3)

    def test_falls_back_to_order_without_team(self):
        found = rank_matches(GAMES, "Dame picks de NBA y NHL hoy")
        self.assertEqual(found, GAMES)

    def test_single_team_query(self):
        found = rank_matches(GAMES, "quiero el partido de Boston")
        self.assertEqual(found[0]["partido"], "Montreal @ Boston")

    def test_does_not_mutate_rows(self):
        before = list(GAMES)
        rank_matches(GAMES, "Toronto")
        self.assertEqual(GAMES, before)

    def test_market_rows_require_two_teams_time_and_league(self):
        from src.match_report import verified_market_rows
        game = {"liga": "NBA", "partido": "Toronto @ Philadelphia", "hora_cdmx": "18:00", "fecha_cdmx": "2026-11-13"}
        base = {"sport":"NBA", "event":"Toronto Raptors vs Philadelphia 76ers",
                "start_local":"18:00", "date_local":"2026-11-13", "market":"h2h", "pick":"Toronto Raptors",
                "book":"Example", "odds":125}
        self.assertEqual(verified_market_rows(game, [base]), [base])
        self.assertEqual(verified_market_rows(game, [dict(base, start_local="19:00")]), [])
        self.assertEqual(verified_market_rows(game, [dict(base, sport="NHL")]), [])
        self.assertEqual(verified_market_rows(game, [dict(base, date_local="2026-11-14")]), [])
        self.assertEqual(verified_market_rows(game, [dict(base, event="Toronto Raptors vs Boston Celtics")]), [])

    def test_ambiguous_odds_are_rejected(self):
        from src.match_report import verified_market_rows
        game = {"liga":"NBA", "partido":"Toronto @ Philadelphia", "hora_cdmx":"18:00", "fecha_cdmx":"2026-11-13"}
        rows = [
            {"sport":"NBA", "event":"Toronto Raptors vs Philadelphia 76ers", "start_local":"18:00", "date_local":"2026-11-13"},
            {"sport":"NBA", "event":"Toronto Exhibition vs Philadelphia Exhibition", "start_local":"18:00", "date_local":"2026-11-13"},
        ]
        self.assertEqual(verified_market_rows(game, rows), [])

    def test_two_team_question_filters_out_other_games(self):
        from src.match_report import relevant_matches
        result, specific = relevant_matches(GAMES, "Analiza Toronto contra Philadelphia hoy")
        self.assertTrue(specific)
        self.assertEqual([g["partido"] for g in result], ["Toronto @ Philadelphia"])

    def test_reversed_matchup_order(self):
        from src.match_report import relevant_matches
        result, specific = relevant_matches(GAMES, "Philadelphia vs Toronto")
        self.assertTrue(specific)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["partido"], "Toronto @ Philadelphia")

    def test_nonexistent_match_returns_no_unrelated_game(self):
        from src.match_report import relevant_matches
        result, specific = relevant_matches(GAMES, "Dallas vs Phoenix")
        self.assertTrue(specific)
        self.assertEqual(result, [])

    def test_broad_question_shows_all_games(self):
        from src.match_report import relevant_matches
        result, specific = relevant_matches(GAMES, "Dame los partidos de NBA y NHL hoy")
        self.assertFalse(specific)
        self.assertEqual(result, GAMES)

    def test_one_team_query_restricts_results(self):
        from src.match_report import relevant_matches
        result, specific = relevant_matches(GAMES, "quiero el partido de Montreal")
        self.assertTrue(specific)
        self.assertEqual([g["partido"] for g in result], ["Montreal @ Boston"])

    def test_nickname_city_alias_requires_unique_match(self):
        from src.match_report import relevant_matches
        rows = [
            {"liga":"NBA", "partido":"L.A. Lakers @ Golden State"},
            {"liga":"NBA", "partido":"Toronto @ Boston"},
        ]
        result, specific = relevant_matches(rows, "Lakers vs Warriors")
        self.assertTrue(specific)
        self.assertEqual(result, [rows[0]])

    def test_shared_city_without_nickname_is_not_a_safe_identity(self):
        from src.match_report import relevant_matches
        rows = [{"liga":"NBA", "partido":"Los Angeles @ Golden State"}]
        found, specific = relevant_matches(rows, "Lakers vs Warriors")
        self.assertTrue(specific)
        self.assertEqual(found, [])
