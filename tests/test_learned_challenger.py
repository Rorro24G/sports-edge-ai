"""Tests: pregame feature extraction, genuine fitting, independent holdout."""
from datetime import date, timedelta
from unittest import TestCase

from src.learned_challenger import (
    FEATURE_KEYS, TRAINING_VERSION, extract_features,
    learn_weights, infer, train_and_compare,
)

DAY = date(2026, 11, 18)


def games(scored: float, allowed: float) -> dict:
    return {"games": [
        {
            "event_id": str(1000+i),
            "date": (DAY - timedelta(days=i+1)).isoformat(),
            "points_for": scored + (i % 4),
            "points_against": allowed + (i % 3),
            "home": i%2 == 0,
        }
        for i in range(10)
    ]}


def audit(year: int, n: int = 125) -> dict:
    details = []
    for i in range(n):
        signal = (((i*17+5)%101)-50)/40
        features = {name: 0.0 for name in FEATURE_KEYS}
        features["form_gap"] = signal
        features["recent_form_gap"] = signal*.9
        features["offense_gap"] = signal*.5
        # Deterministic signal with a small, reproducible disturbance.
        actual_home = signal + ((((i*29)%23)-11)/20) > 0
        details.append({
            "event_id": f"{year}-{i}",
            "date": f"{year}-11-18",
            "last_feature_date": f"{year}-11-16",
            "pregame_features": features,
            "p_home_experimental": .5,
            "actual_home": actual_home,
        })
    return {
        "version": "SEAI-JUICIO-0.2", "sport": "NBA",
        "source": "ESPN scoreboard + ESPN team schedules",
        "data_complete": True,
        "model_validated": False, "model_calibrated": False,
        "period": {"start": f"{year}-10-20", "end": f"{year}-11-30"},
        "details": details,
    }


class ChallengerTests(TestCase):
    def test_features_require_history_and_ignore_future_games(self):
        away = games(116, 98)
        home = games(102, 109)
        original = extract_features("NBA", away, home, DAY)
        self.assertIsNotNone(original)
        self.assertEqual(set(original["features"]), set(FEATURE_KEYS))
        self.assertLess(date.fromisoformat(original["max_history_date"]), DAY)
        away["games"].append({
            "event_id": "9999", "date": (DAY+timedelta(days=2)).isoformat(),
            "points_for": 300, "points_against": 0, "home": True,
        })
        home["games"].append({
            "event_id": "9998", "date": DAY.isoformat(),
            "points_for": 300, "points_against": 0, "home": True,
        })
        self.assertEqual(original, extract_features("NBA", away, home, DAY))
        self.assertIsNone(extract_features("NBA", {"games":[]}, home, DAY))
        self.assertIsNone(extract_features("MLB", away, home, DAY))
        self.assertEqual(original["feature_version"], TRAINING_VERSION)

    def test_train_on_prior_season_and_score_later_holdout(self):
        training = audit(2025)
        holdout = audit(2026)
        result = train_and_compare(training, holdout)
        self.assertEqual(result["trained_model"], TRAINING_VERSION)
        self.assertEqual(result["train_count"], 125)
        self.assertEqual(result["holdout_count"], 125)
        self.assertFalse(result["production_enabled"])
        self.assertFalse(result["train_uses_holdout"])
        self.assertFalse(result["used_covers_to_train"])
        self.assertLess(result["learned_model_holdout"]["brier"],
                        result["old_model_holdout"]["brier"])
        features = {k: 0 for k in FEATURE_KEYS}
        features["form_gap"] = 1.5
        high = infer(result["model"], features)
        features["form_gap"] = -1.5
        low = infer(result["model"], features)
        self.assertGreater(high, low)

    def test_training_does_not_change_when_holdout_outcomes_change(self):
        prior = audit(2025)
        next_year = audit(2026)
        original = train_and_compare(prior, next_year)
        for row in next_year["details"]:
            row["actual_home"] = not row["actual_home"]
        changed = train_and_compare(prior, next_year)
        self.assertEqual(original["model"], changed["model"])
        self.assertNotEqual(original["learned_model_holdout"],
                            changed["learned_model_holdout"])

    def test_reject_reverse_split_overlaps_and_wrong_sport(self):
        with self.assertRaisesRegex(ValueError, "preceder"):
            train_and_compare(audit(2026), audit(2025))
        changed = audit(2026)
        changed["sport"] = "NFL"
        with self.assertRaisesRegex(ValueError, "separados"):
            train_and_compare(audit(2025), changed)
        changed = audit(2026)
        changed["details"][0]["event_id"] = audit(2025)["details"][0]["event_id"]
        with self.assertRaisesRegex(ValueError, "mismos encuentros"):
            train_and_compare(audit(2025), changed)

    def test_reject_any_future_leak_or_incomplete_source(self):
        prior = audit(2025)
        prior["details"][0]["last_feature_date"] = "2025-11-18"
        with self.assertRaisesRegex(ValueError, "FUGA DE DATOS"):
            train_and_compare(prior, audit(2026))
        prior = audit(2025)
        prior["data_complete"] = False
        with self.assertRaisesRegex(ValueError, "incompleta"):
            train_and_compare(prior, audit(2026))
        prior = audit(2025)
        prior["details"][0]["pregame_features"]["coves_pick"] = 1.0
        with self.assertRaisesRegex(ValueError, "inválidas"):
            train_and_compare(prior, audit(2026))

    def test_small_training_sample_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "insuficiente"):
            train_and_compare(audit(2025, n=40), audit(2026))
