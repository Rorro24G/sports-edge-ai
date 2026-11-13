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
        game = {"liga": "NBA", "partido": "Toronto @ Philadelphia", "hora_cdmx": "18:00"}
        base = {"sport":"NBA", "event":"Toronto Raptors vs Philadelphia 76ers",
                "start_local":"18:00", "market":"h2h", "pick":"Toronto Raptors",
                "book":"Example", "odds":125}
        self.assertEqual(verified_market_rows(game, [base]), [base])
        self.assertEqual(verified_market_rows(game, [dict(base, start_local="19:00")]), [])
        self.assertEqual(verified_market_rows(game, [dict(base, sport="NHL")]), [])
        self.assertEqual(verified_market_rows(game, [dict(base, event="Toronto Raptors vs Boston Celtics")]), [])

    def test_ambiguous_odds_are_rejected(self):
        from src.match_report import verified_market_rows
        game = {"liga":"NBA", "partido":"Toronto @ Philadelphia", "hora_cdmx":"18:00"}
        rows = [
            {"sport":"NBA", "event":"Toronto Raptors vs Philadelphia 76ers", "start_local":"18:00"},
            {"sport":"NBA", "event":"Toronto Exhibition vs Philadelphia Exhibition", "start_local":"18:00"},
        ]
        self.assertEqual(verified_market_rows(game, rows), [])
