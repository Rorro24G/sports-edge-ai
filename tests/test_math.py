import unittest
from src.math_utils import (american_to_decimal, implied_probability, expected_roi,
                            no_vig_probabilities, ParlayLeg, independent_parlay)
from src.market_reference import build_market_rows


class MathTests(unittest.TestCase):
    def test_plus_225(self):
        self.assertAlmostEqual(american_to_decimal(225), 3.25)
        self.assertAlmostEqual(implied_probability(225), 1 / 3.25)
        self.assertAlmostEqual(expected_roi(3.25, .37), .2025)

    def test_negative_110(self):
        self.assertAlmostEqual(american_to_decimal(-110), 1 + 100 / 110)

    def test_no_vig_sums_one(self):
        self.assertAlmostEqual(sum(no_vig_probabilities({"A": -110, "B": -110}).values()), 1.0)

    def test_probability_bounds(self):
        with self.assertRaises(ValueError):
            expected_roi(3.25, 1.05)

    def test_parlay_blocked_if_correlation_not_evaluated(self):
        legs = [ParlayLeg("G1", 1.9, .5), ParlayLeg("G2", 2.2, .4)]
        with self.assertRaises(ValueError):
            independent_parlay(legs)

    def test_parlay_same_event_blocked(self):
        legs = [ParlayLeg("G1", 1.9, .5), ParlayLeg("G1", 2.2, .4)]
        with self.assertRaises(ValueError):
            independent_parlay(legs, independence_validated=True)

    def test_market_comparison_is_not_a_prediction(self):
        event={"id":"E1", "_sport_name":"NBA", "away_team":"A", "home_team":"B",
               "bookmakers":[
                 {"key":"b1","markets":[{"key":"h2h","outcomes":[{"name":"A","price":110},{"name":"B","price":-130}]}]},
                 {"key":"b2","markets":[{"key":"h2h","outcomes":[{"name":"A","price":105},{"name":"B","price":-125}]}]},
                 {"key":"b3","markets":[{"key":"h2h","outcomes":[{"name":"A","price":100},{"name":"B","price":-120}]}]},
               ]}
        rows=build_market_rows([event])
        self.assertEqual(len(rows),6)
        self.assertTrue(all(row["recommendation"]=="SIN_RECOMENDACION" for row in rows))
        self.assertTrue(all(row["peer_count"]==2 for row in rows))


if __name__ == "__main__":
    unittest.main()
