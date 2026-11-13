from unittest import TestCase
from src.market_summary import implied_percent, game_market_probabilities


class ImpliedMarketTests(TestCase):
    def test_known_prices(self):
        self.assertEqual(implied_percent("+100"), 50.0)
        self.assertEqual(implied_percent("-110"), 52.38)
        self.assertEqual(implied_percent("+150"), 40.0)
        self.assertEqual(implied_percent("-200"), 66.67)

    def test_bad_prices_do_not_invent_probabilities(self):
        for value in [None, "", "54%", "o223.5 -110", "-98", "0", "NaN", True, float("inf")]:
            self.assertIsNone(implied_percent(value))

    def test_each_side_independent_no_false_vig_removal(self):
        row = game_market_probabilities({
            "momio_visitante": "+240", "momio_local": None
        })
        self.assertEqual(row["visitante"], 29.41)
        self.assertIsNone(row["local"])
