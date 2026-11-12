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
