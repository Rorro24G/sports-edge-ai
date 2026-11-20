"""Simulation visuals are based on honest reproducible draws."""
from unittest import TestCase

from src.simulations import GameScenario, simulate_totals
from src.simulation_view import _scene, _distribution_meter


class SimulationDistributionTests(TestCase):
    def test_reproducible_histogram_and_quantiles(self):
        scenario = GameScenario(
            "NFL", 23.3, 25.5, 8.3, 7.9, 0.0, 48.5,
            simulations=10000, seed=99,
        )
        a = simulate_totals(scenario)
        b = simulate_totals(scenario)
        self.assertEqual(a.histogram, b.histogram)
        self.assertEqual(sum(x["Frecuencia"] for x in a.histogram), 10000)
        self.assertLessEqual(a.simulated_p10_total, a.simulated_median_total)
        self.assertLessEqual(a.simulated_median_total, a.simulated_p90_total)
        self.assertEqual(a.over_count + a.under_count + a.push_count, 10000)
        self.assertEqual(a.status, "ESCENARIO_NO_VALIDADO")

    def test_empirical_bootstrap_uses_real_results_and_is_deterministic(self):
        history = (94.0, 112.0, 124.0, 98.0, 110.0, 107.0,
                   109.0, 117.0, 97.0, 122.0)
        allowed = (101.0, 115.0, 96.0, 118.0, 107.0, 112.0,
                   100.0, 104.0, 109.0, 95.0)
        scenario = GameScenario(
            "NBA", 109.1, 112.3, 12.5, 11.7, 0.0, 224.5,
            simulations=10000, seed=10,
            away_scored=history, away_allowed=allowed,
            home_scored=tuple(reversed(history)),
            home_allowed=tuple(reversed(allowed)),
        )
        a, b = simulate_totals(scenario), simulate_totals(scenario)
        self.assertEqual(a.simulation_method, "BOOTSTRAP_ESPN_RECIENTE")
        self.assertEqual(a.histogram, b.histogram)
        self.assertEqual(sum(x["Frecuencia"] for x in a.histogram), 10000)
        self.assertEqual(a.over_count + a.under_count + a.push_count, 10000)
        self.assertNotEqual(a.simulation_method, "GAUSSIANA_EXPLORATORIA")

    def test_incomplete_histories_rejected_before_bootstrap(self):
        with self.assertRaisesRegex(ValueError, "Bootstrap"):
            simulate_totals(GameScenario(
                "NBA", 100, 104, 10, 11, 0, 220.5,
                away_scored=(100.0,), away_allowed=(95.0,)
            ))

    def test_visual_meters_use_actual_simulation_outcomes(self):
        scenario = GameScenario(
            "NBA", 110, 115, 11, 10, 0.0, 223.5,
            simulations=10000, seed=42,
        )
        result = simulate_totals(scenario)
        html = _distribution_meter(result)
        self.assertIn("TOTAL · OVER", html)
        self.assertIn("LOCAL GANA · SIMULADO", html)
        self.assertIn(f"{result.home_win_probability*100:.1f}%", html)
        self.assertIn("sim-fill-shine", html)
        self.assertNotIn("<script>", html)

    def test_nba_court_and_nfl_field_are_original_and_labeled(self):
        nfl = _scene("NFL", 'Visitante <script>', "Local", 22, 24)
        self.assertIn("LABORATORIO 10.000", nfl)
        self.assertIn("Ilustración animada de NFL", nfl)
        self.assertNotIn("<script>", nfl)
        self.assertIn("VISUALIZACIÓN ILUSTRATIVA", nfl)
        nba = _scene("NBA", "Lakers", "Warriors", 110, 115)
        self.assertIn("Ilustración animada de NBA", nba)
        self.assertIn("Lakers", nba)
        self.assertIn("Warriors", nba)
