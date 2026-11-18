"""Historical reports must never be mistaken for a calibrated live model."""
from __future__ import annotations

from datetime import date, timedelta
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from src.independent_picks import VERSION
from src.model_audit_ui import load_model_audit, load_model_audits, load_calibration_experiment
from src.pick_walkforward import wilson_interval, calibration_bins, walkforward


REPORT = {
    "version": VERSION,
    "source": "ESPN scoreboard + ESPN team schedules",
    "model_validated": False, "model_calibrated": False,
    "data_complete": True,
    "evaluated_count": 160, "candidate_count": 93,
    "correct_candidates": 75,
    "candidate_accuracy_observed": 75/93,
    "brier_all_evaluated": 0.19013,
    "validation_status": "AUDITORIA_DESCRIPTIVA",
    "calibration_bins": [
        {"range": f"{i*20}-{(i+1)*20}%", "n": 32,
         "avg_predicted_home": .2+.15*i,
         "actual_home_frequency": .2+.15*i}
        for i in range(5)
    ],
    "period": {"start": "2025-11-10", "end": "2025-12-02"},
    "sport": "NBA",
}


def fixture(day, game_id, away_score, home_score):
    return {
        "sport": "NBA", "event_id": str(game_id), "local_date": day,
        "status": "POST",
        "away": "Road", "home": "Home",
        "away_team_id": "1", "home_team_id": "2",
        "away_score": away_score, "home_score": home_score,
    }


def history(target, points, allowed):
    return {"games": [{
        "date": (target - timedelta(days=i+1)).isoformat(),
        "event_id": str(1000+i), "points_for": points+(i%3),
        "points_against": allowed+(i%2), "home": bool(i%2),
    } for i in range(10)]}


class AuditQualityTests(TestCase):
    def test_wilson_interval_extremes_and_invalid_samples(self):
        self.assertIsNone(wilson_interval(0, 0))
        self.assertIsNone(wilson_interval(3, 2))
        self.assertEqual(wilson_interval(0, 10)[0], 0.0)
        self.assertEqual(wilson_interval(10, 10)[1], 1.0)
        lo, hi = wilson_interval(75, 93)
        self.assertLess(lo, .8065)
        self.assertGreater(hi, .8065)

    def test_calibration_bins_do_not_train_on_outcomes(self):
        rows = [
            {"p_home_experimental": .25, "actual_home": False},
            {"p_home_experimental": .25, "actual_home": True},
            {"p_home_experimental": .8, "actual_home": True},
        ]
        bins = calibration_bins(rows)
        self.assertEqual(bins[1]["n"], 2)
        self.assertEqual(bins[1]["avg_predicted_home"], .25)
        self.assertEqual(bins[1]["actual_home_frequency"], .5)
        self.assertEqual(bins[4]["n"], 1)

    def test_audit_uses_fair_home_only_baseline_on_same_candidates(self):
        day = date(2026, 11, 17)
        result = walkforward(
            [fixture(day, "904", 120, 98)],
            {("NBA", "1"): history(day, 127, 99),
             ("NBA", "2"): history(day, 92, 117)},
            minimum_evaluated=1, minimum_candidates=1,
        )
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["correct_candidates"], 1)
        self.assertEqual(result["home_only_accuracy_on_candidates"], 0)
        self.assertEqual(result["home_only_accuracy_evaluated"], 0)
        self.assertGreater(result["avg_estimated_probability_on_candidates"], .5)
        self.assertEqual(len(result["calibration_bins"]), 5)
        self.assertIsNotNone(result["calibration_gap_ece_exploratory"])
        self.assertFalse(result["model_validated"])
        self.assertFalse(result["model_calibrated"])

    def test_historical_bundle_and_calibration_are_version_and_date_bound(self):
        train = dict(REPORT)
        test = dict(
            REPORT, period={"start": "2026-10-28", "end": "2026-11-17"},
            evaluated_count=101, candidate_count=58, correct_candidates=46,
            candidate_accuracy_observed=46/58, brier_all_evaluated=.21343,
            calibration_bins=[
                {"range": f"{i*20}-{(i+1)*20}%", "n": (21 if i == 0 else 20),
                 "avg_predicted_home": .3, "actual_home_frequency": .3}
                for i in range(5)
            ]
        )
        bundle = {
            "model": VERSION,
            "reports": [train, test],
            "calibration_experiment": {
                "status": "EXPERIMENTO_CALIBRACION_SIN_ACTIVAR",
                "sport": "NBA", "base_model": VERSION,
                "production_enabled": False, "model_validated": False,
                "fit_uses_holdout": False, "train_count": 160,
                "holdout_count": 101, "train_period": train["period"],
                "holdout_period": test["period"],
                "raw_holdout": {"brier": .21343},
                "calibrated_holdout": {"brier": .211057},
            },
        }
        with TemporaryDirectory() as temp:
            path = Path(temp)/"bundle.json"
            def write(doc):
                path.write_text(json.dumps(doc), encoding="utf-8")
            write(bundle)
            reports = load_model_audits(path)
            self.assertEqual(len(reports), 2)
            self.assertIsNotNone(load_calibration_experiment(path))
            changed = deepcopy(bundle)
            changed["calibration_experiment"]["production_enabled"] = True
            write(changed)
            self.assertIsNone(load_calibration_experiment(path))
            changed = deepcopy(bundle)
            changed["reports"][0]["version"] = "old-model"
            write(changed)
            self.assertEqual(load_model_audits(path), [])

    def test_ui_does_not_accept_wrong_version_or_bad_source_or_incomplete_sample(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)/"audit.json"
            def read(report):
                path.write_text(json.dumps(report), encoding="utf-8")
                return load_model_audit(path)
            self.assertIsNotNone(read(dict(REPORT)))
            self.assertIsNone(read(dict(REPORT, version="SEAI-JUICIO-0.1")))
            self.assertIsNone(read(dict(REPORT, source="example.com")))
            self.assertIsNone(read(dict(REPORT, data_complete=False)))
            self.assertIsNone(read(dict(REPORT, candidate_count=4)))
            self.assertIsNone(read(dict(REPORT, model_validated=True)))
            self.assertIsNone(read(dict(REPORT, model_calibrated=True)))
