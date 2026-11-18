"""Historical opponent quality can veto weak judgments, never invent them."""
from datetime import date, timedelta
from unittest import TestCase

from src.opponent_quality import (
    event_team_index, team_opponent_quality, challenge_pick, compare_challenger
)
from src.independent_picks import predict_from_results


DAY = date(2026, 11, 18)


def team_data(team_id: str, *, pf=120, pa=105, first_ago=1, games=18,
              sport="NBA") -> dict:
    """Two participating teams use the same event IDs, different own scores."""
    return {
        "games": [{
            "event_id": str(10000+i),
            "date": (DAY-timedelta(days=first_ago+i)).isoformat(),
            "points_for": pf+(i%3), "points_against": pa+(i%2),
            "home": bool(i%2),
        } for i in range(games)]
    }


def league_data():
    """Historical head-to-head records with actual same-event links."""
    out = {
        ("NBA", "1"): team_data("1", pf=129, pa=96),
        ("NBA", "2"): team_data("2", pf=96, pa=129),
        ("NBA", "3"): team_data("3", pf=90, pa=110),
    }
    # Every event 10000... represents 1 vs 2. Third team has other events.
    out[("NBA", "3")]["games"] = [
        dict(r, event_id=str(30000+i))
        for i, r in enumerate(out[("NBA", "3")]["games"])
    ]
    return out


class OpponentStrengthTests(TestCase):
    def test_only_historical_opponents_and_no_future_leakage(self):
        histories = league_data()
        idx = event_team_index(histories, "NBA")
        score = team_opponent_quality("NBA", "1", DAY, histories, idx)
        self.assertTrue(score["available"])
        self.assertGreaterEqual(score["matched_opponents"], 4)
        self.assertLess(score["difficulty"], 0)  # opponent team 2 weak
        histories[("NBA", "2")]["games"].append({
            "event_id": "99999", "date": (DAY+timedelta(days=5)).isoformat(),
            "points_for": 300, "points_against": 0,
        })
        self.assertEqual(
            team_opponent_quality("NBA", "1", DAY, histories,
                                  event_team_index(histories, "NBA")),
            score,
        )

    def test_no_data_coverage_means_no_opponent_verdict(self):
        histories = league_data()
        histories.pop(("NBA", "2"))
        idx = event_team_index(histories, "NBA")
        baseline = {"status": "CANDIDATO_EXPERIMENTAL",
                    "side": "local", "margin_experimental": 6.0}
        verdict = challenge_pick(
            "NBA", "1", "3", DAY, baseline, histories, index=idx
        )
        self.assertFalse(verdict["assessable"])
        self.assertFalse(verdict["veto"])

    def test_rejects_score_of_unrelated_event(self):
        histories = league_data()
        # Opponent 3 has scores but none linked by event ID to team 1.
        idx = event_team_index(histories, "NBA")
        check = team_opponent_quality("NBA", "3", DAY, histories, idx)
        self.assertFalse(check["available"])

    def test_only_vetoes_existing_candidate_and_never_flips_winner(self):
        histories = league_data()
        idx = event_team_index(histories, "NBA")
        result = challenge_pick(
            "NBA", "1", "2", DAY,
            {"status": "PASAR", "side": "visitante",
             "margin_experimental": 3.0}, histories, index=idx
        )
        self.assertEqual(result["verdict"], "NO_BASELINE_PICK")
        self.assertFalse(result["veto"])
        valid = challenge_pick(
            "NBA", "1", "2", DAY,
            {"status": "CANDIDATO_EXPERIMENTAL",
             "side": "visitante", "margin_experimental": 2.0},
            histories, index=idx
        )
        self.assertTrue(valid["assessable"])
        self.assertIn(valid["verdict"], {"CONSISTENT", "VETO"})
        self.assertFalse(valid["production_enabled"])
        self.assertEqual(valid["baseline_side"], "visitante")


class ChallengerAuditTests(TestCase):
    def test_challenger_does_not_claim_edge_or_promote_itself(self):
        histories = league_data()
        game_day = DAY-timedelta(days=1)
        fixture = {
            "sport": "NBA", "event_id": "20000", "local_date": game_day,
            "status": "POST", "away_team_id": "1", "home_team_id": "2",
            "away": "Road", "home": "House",
            "away_score": 124, "home_score": 98,
        }
        # Ensure at least 7 prior team games before fixture date.
        report = compare_challenger([fixture], histories, minimum_evaluated=1)
        self.assertEqual(report["model"], "SEAI-RIVALES-0.3-EXPERIMENTAL")
        self.assertFalse(report["eligible_for_promotion"])
        self.assertFalse(report["production_enabled"])
        self.assertGreaterEqual(report["historical_baseline_candidates"], 0)
        self.assertEqual(
            report["assessable_candidates"] + report["unassessable_candidates"],
            report["historical_baseline_candidates"],
        )
