"""SEAI judgement v0.2: conservative evidence checks and chronological auditing."""
from datetime import date, timedelta
from unittest import TestCase

from src.independent_picks import VERSION, predict_from_results
from src.pick_judgement import judge
from src.pick_walkforward import walkforward

DAY = date(2026, 11, 17)


def games(points, conceded, *, venue=None, shift=0, count=10):
    rows = []
    for i in range(count):
        if isinstance(points, list):
            pf = points[i]
        else:
            pf = points + (i % 3)
        if isinstance(conceded, list):
            pa = conceded[i]
        else:
            pa = conceded + (i % 2)
        rows.append({
            "date": (DAY-timedelta(days=i+1+shift)).isoformat(),
            "event_id": str(5000+i), "points_for": pf,
            "points_against": pa, "home": venue if venue is not None else bool(i % 2),
        })
    return {"games": rows}


class SEAIJudgementTests(TestCase):
    def test_multisignal_consistency_allows_robust_decision(self):
        result = predict_from_results(
            "NBA", "Away", "Home", games(124, 96), games(91, 118), DAY
        )
        self.assertEqual(result["status"], "CANDIDATO_EXPERIMENTAL")
        self.assertEqual(result["team"], "Away")
        self.assertEqual(result["contradictions"], [])
        self.assertEqual(result["stability"], 1)
        self.assertIn("Últimos 5", result["evidence"])
        self.assertIn("Según localía real", result["evidence"])
        self.assertFalse(result["model_validated"])
        self.assertFalse(result["market_input_used"])
        self.assertEqual(result["version"], VERSION)

    def test_anomalous_one_game_does_not_force_pick(self):
        # A single 200-point outlier would skew the old weighted-score model.
        away = games([200]+[100]*9, [100]*10)
        home = games([99]*10, [100]*10)
        result = predict_from_results("NBA", "Away", "Home", away, home, DAY)
        self.assertEqual(result["status"], "PASAR")
        self.assertTrue(result["contradictions"])
        self.assertEqual(result["stake"], 0)

    def test_selection_does_not_depend_only_on_assumed_home_bonus(self):
        r = predict_from_results("NBA", "Away", "Home",
                                 games(105, 105), games(106, 105), DAY)
        self.assertEqual(r["status"], "PASAR")
        self.assertTrue(any("localía" in reason or "demasiado" in reason
                            for reason in r["contradictions"]))

    def test_stale_history_is_vetoed(self):
        old_away = games(130, 94, shift=37)
        old_home = games(88, 119, shift=37)
        r = predict_from_results("NBA", "Away", "Home", old_away, old_home, DAY)
        self.assertEqual(r["status"], "PASAR")
        self.assertTrue(any("antiguos" in x for x in r["contradictions"]))

    def test_no_future_result_and_out_of_order_events(self):
        home = games(95, 118)
        away = games(124, 96)
        control = predict_from_results("NBA", "Away", "Home", away, home, DAY)
        away["games"].append({
            "date": (DAY+timedelta(days=1)).isoformat(),
            "event_id": "80000", "points_for": 0,
            "points_against": 300,
        })
        home["games"] = list(reversed(home["games"]))
        check = predict_from_results("NBA", "Away", "Home", away, home, DAY)
        self.assertEqual(control, check)


class SEAIWalkForwardTests(TestCase):
    def test_uses_only_history_prior_to_each_fixture(self):
        base_away = games(126, 96)
        base_home = games(92, 118)
        days = [DAY-timedelta(days=x) for x in (3, 2, 1)]
        fixtures = [{
            "sport": "NBA", "event_id": str(900+i),
            "away_team_id": "1", "home_team_id": "2",
            "away": "Road", "home": "House",
            "status": "POST", "local_date": day,
            "away_score": 122, "home_score": 95,
        } for i, day in enumerate(days)]
        histories = {("NBA", "1"): base_away, ("NBA", "2"): base_home}
        report = walkforward(fixtures, histories, minimum_evaluated=1,
                             minimum_candidates=1)
        self.assertEqual(report["version"], VERSION)
        self.assertEqual(report["evaluated_count"], 3)
        self.assertEqual(report["candidate_count"], 3)
        self.assertEqual(report["correct_candidates"], 3)
        self.assertEqual(report["candidate_accuracy_observed"], 1.0)
        self.assertIsNotNone(report["brier_all_evaluated"])
        self.assertFalse(report["model_validated"])
        self.assertFalse(report["model_calibrated"])
        self.assertEqual(report["validation_status"], "AUDITORIA_DESCRIPTIVA")
        insufficient = walkforward(fixtures, histories)
        self.assertEqual(insufficient["validation_status"], "MUESTRA_INSUFICIENTE")

    def test_skips_nonfinal_and_duplicate_games(self):
        single = {
            "sport": "NBA", "event_id": "9", "away_team_id": "1", "home_team_id": "2",
            "away": "Road", "home": "House", "status": "POST",
            "local_date": DAY-timedelta(days=1),
            "away_score": 120, "home_score": 100,
        }
        report = walkforward(
            [single, dict(single), dict(single, status="PRE")],
            {("NBA", "1"): games(126, 90),
             ("NBA", "2"): games(92, 118)},
            minimum_evaluated=1, minimum_candidates=1,
        )
        self.assertEqual(report["fixture_count"], 1)
        self.assertEqual(report["evaluated_count"], 1)
        self.assertEqual(report["details"][0]["date"],
                         (DAY-timedelta(days=1)).isoformat())
