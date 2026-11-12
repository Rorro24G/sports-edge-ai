import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.simulations import GameScenario, simulate_totals
from src.web_data import find_games, load_fixture
from src.web_query import interpret_request

NOW = datetime(2026, 11, 12, 2, 20, tzinfo=ZoneInfo("America/Mexico_City"))


class QueryTests(unittest.TestCase):
    def test_explicit_date_and_sports(self):
        result = interpret_request(
            "Hoy 20 de noviembre quiero NFL y NBA con picks y un parlay", now=NOW
        )
        self.assertEqual(result.target_date, date(2026, 11, 20))
        self.assertEqual(result.sports, ("NFL", "NBA"))
        self.assertTrue(result.wants_picks)
        self.assertTrue(result.wants_parlay)

    def test_tomorrow_from_mexico(self):
        result = interpret_request("tenis mañana", now=NOW)
        self.assertEqual(result.target_date, date(2026, 11, 13))
        self.assertEqual(result.sports, ("ATP", "WTA"))

    def test_all_sports_default(self):
        result = interpret_request("Dame los mejores picks de hoy", now=NOW)
        self.assertEqual(result.sports, ("NFL", "NBA", "NHL", "ATP", "WTA"))
        self.assertEqual(result.target_date, date(2026, 11, 12))

    def test_iso_date_priority(self):
        result = interpret_request("mañana 2026-11-20 NHL", now=NOW)
        self.assertEqual(result.target_date, date(2026, 11, 20))

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            interpret_request("32 de noviembre de 2026 NBA", now=NOW)


class ScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture()

    def test_noncovered_date_does_not_claim_no_games(self):
        result = find_games(self.fixture, date(2026, 11, 20), ("NFL", "NBA"))
        self.assertFalse(result.date_covered)
        self.assertEqual(len(result.games), 0)

    def test_tennis_is_explicitly_missing(self):
        result = find_games(self.fixture, date(2026, 11, 13), ("ATP",))
        self.assertEqual(result.missing_sports, ("ATP",))
        self.assertEqual(result.games, ())

    def test_known_snapshot_has_games_and_sources(self):
        result = find_games(self.fixture, date(2026, 11, 13), ("NBA", "NHL"))
        self.assertTrue(result.date_covered)
        self.assertGreater(len(result.games), 0)
        self.assertTrue(all(r["source_url"].startswith("https://") for r in result.games))
        self.assertTrue(all(r["prediction_status"] == "SIN_MODELO_VALIDADO" for r in result.games))


class MonteCarloTests(unittest.TestCase):
    def setUp(self):
        self.inputs = GameScenario("NFL", 22, 24, 9, 9, 0.05, 45.5, 10000, 12)

    def test_probabilities_and_counts(self):
        result = simulate_totals(self.inputs)
        self.assertEqual(result.over_count + result.under_count + result.push_count, 10000)
        self.assertAlmostEqual(
            result.over_probability + result.under_probability + result.push_probability, 1.0
        )
        self.assertEqual(result.status, "ESCENARIO_NO_VALIDADO")

    def test_seed_is_reproducible(self):
        self.assertEqual(simulate_totals(self.inputs), simulate_totals(self.inputs))

    def test_invalid_correlation(self):
        with self.assertRaises(ValueError):
            simulate_totals(GameScenario("NFL", 22, 24, 9, 9, 1.0, 45.5))

    def test_invalid_simulation_count(self):
        with self.assertRaises(ValueError):
            simulate_totals(GameScenario("NFL", 22, 24, 9, 9, 0.0, 45.5, 100))
