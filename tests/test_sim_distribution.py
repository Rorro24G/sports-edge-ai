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
