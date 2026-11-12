"""Pruebas del control de valor esperado y tamaños de apuesta."""
import unittest
from src.staking import assess_bet

class StakingTests(unittest.TestCase):
    def test_45_percent_is_negative_at_minus_110(self):
        x=assess_bet(-110,.45,model_validated=True,probability_lower_bound=.42)
        self.assertLess(x.expected_roi,0)
        self.assertEqual(x.suggested_bankroll_fraction,0)

    def test_45_percent_has_12_5_percent_expected_roi_at_plus_150(self):
        x=assess_bet(150,.45)
        self.assertAlmostEqual(x.expected_roi,.125)
        self.assertAlmostEqual(x.implied_probability,.4)
        self.assertEqual(x.suggested_bankroll_fraction,0)

    def test_no_stake_without_validation(self):
        x=assess_bet(150,.45,probability_lower_bound=.42)
        self.assertEqual(x.status,'MODELO_SIN_VALIDAR')
        self.assertEqual(x.suggested_bankroll_fraction,0)

    def test_stake_with_conservative_edge_and_validated_model(self):
        x=assess_bet(150,.45,model_validated=True,probability_lower_bound=.42)
        self.assertEqual(x.status,'CANDIDATO_PARA_REVISION')
        self.assertAlmostEqual(x.suggested_bankroll_fraction,1/120,places=7)

    def test_uncertainty_lower_bound_blocks_stake(self):
        self.assertEqual(assess_bet(150,.45,model_validated=True,probability_lower_bound=.4).suggested_bankroll_fraction,0)

    def test_absent_lower_bound_blocks_stake(self):
        x=assess_bet(150,.45,model_validated=True)
        self.assertEqual(x.status,'FALTA_INTERVALO_DE_INCERTIDUMBRE')
        self.assertEqual(x.suggested_bankroll_fraction,0)

    def test_cap_is_enforced(self):
        self.assertAlmostEqual(assess_bet(200,.8,model_validated=True,probability_lower_bound=.7).suggested_bankroll_fraction,.01)

    def test_invalid_parameters(self):
        for odds, p in [(0,.5),(90,.5),(-90,.5),(200,1.2)]:
            with self.assertRaises(ValueError):
                assess_bet(odds,p)
        with self.assertRaises(ValueError):
            assess_bet(150,.45,probability_lower_bound=.5)

if __name__=='__main__':
    unittest.main()
