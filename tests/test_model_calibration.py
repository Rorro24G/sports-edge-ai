"""Temporal calibration is an isolated experiment, not an automatic live model."""
from copy import deepcopy
from unittest import TestCase

from src.model_calibration import PlattMap, evaluate_calibration


def audit(year: int, n: int = 120) -> dict:
    details = []
    for i in range(n):
        p = .23 + .54*((i * 17) % 100)/99
        observed = ((i * 47 + year) % 100) < (p*100)
        details.append({
            "event_id": f"{year}-{i}",
            "p_home_experimental": round(p, 4),
            "actual_home": observed,
        })
    return {
        "version": "SEAI-JUICIO-0.2", "sport": "NBA",
        "source": "ESPN scoreboard + ESPN team schedules",
        "data_complete": True, "model_validated": False,
        "period": {"start": f"{year}-10-01", "end": f"{year}-12-01"},
        "details": details,
    }


class PlattTests(TestCase):
    def test_train_only_2025_then_evaluate_2026(self):
        report = evaluate_calibration(audit(2025), audit(2026))
        self.assertEqual(report["status"], "EXPERIMENTO_CALIBRACION_SIN_ACTIVAR")
        self.assertEqual(report["train_count"], 120)
        self.assertEqual(report["holdout_count"], 120)
        self.assertFalse(report["production_enabled"])
        self.assertFalse(report["fit_uses_holdout"])
        self.assertFalse(report["model_validated"])
        self.assertGreater(report["platt_slope"], 0)
        self.assertLessEqual(report["raw_holdout"]["brier"], 1)
        self.assertLessEqual(report["calibrated_holdout"]["brier"], 1)
        self.assertIn("brier_change_calibrated_minus_raw", report)
        mapper = PlattMap(report["platt_slope"], report["platt_intercept"],
                          120, 1.0)
        self.assertLess(mapper.predict(.25), mapper.predict(.75))

    def test_reject_reverse_training_test_or_overlap(self):
        with self.assertRaisesRegex(ValueError, "DESPUÉS"):
            evaluate_calibration(audit(2026), audit(2025))
        overlapping = audit(2025)
        with self.assertRaisesRegex(ValueError, "DESPUÉS"):
            evaluate_calibration(audit(2025), overlapping)

    def test_reject_wrong_sport_and_version_and_incomplete_inputs(self):
        baseline = audit(2025)
        altered = audit(2026)
        altered["sport"] = "NHL"
        with self.assertRaisesRegex(ValueError, "deportes"):
            evaluate_calibration(baseline, altered)
        altered["sport"] = "NBA"
        altered["version"] = "FAKE"
        with self.assertRaisesRegex(ValueError, "versión"):
            evaluate_calibration(baseline, altered)
        altered["version"] = baseline["version"]
        altered["data_complete"] = False
        with self.assertRaisesRegex(ValueError, "incompletos"):
            evaluate_calibration(baseline, altered)

    def test_reject_duplicate_or_corrupted_training_examples(self):
        historical = audit(2025)
        future = audit(2026)
        historical["details"][1]["event_id"] = historical["details"][0]["event_id"]
        with self.assertRaisesRegex(ValueError, "duplicado"):
            evaluate_calibration(historical, future)
        historical = audit(2025)
        historical["details"][0]["p_home_experimental"] = 1.0
        with self.assertRaisesRegex(ValueError, "utilizable"):
            evaluate_calibration(historical, future)
        historical = audit(2025, n=10)
        with self.assertRaisesRegex(ValueError, "Muestra insuficiente"):
            evaluate_calibration(historical, future)
