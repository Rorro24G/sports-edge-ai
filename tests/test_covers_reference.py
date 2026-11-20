"""Validar enlaces públicos por liga sin llamadas externas."""
import unittest
from src.covers_reference import picks_links, COVERS_PAGES


class CoversReferenceTests(unittest.TestCase):
    def test_all_three_leagues(self):
        result = picks_links(("NFL", "NBA", "NHL"))
        self.assertEqual(tuple(league for league, _ in result), ("NBA", "NFL", "NHL"))
        self.assertTrue(all(url.startswith("https://www.covers.com/picks/") for _, url in result))

    def test_no_unverified_tennis_link(self):
        self.assertEqual(picks_links(("ATP", "WTA")), ())
        self.assertEqual(picks_links(("NBA", "NBA")), (("NBA", COVERS_PAGES["NBA"]),))
