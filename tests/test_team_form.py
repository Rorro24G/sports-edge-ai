"""ESPN historical-team form must never use target-date or future results."""
from datetime import date, timedelta
from unittest import TestCase

from src.team_form import (
    completed_team_games, recent_team_form, scenario_from_forms, scenario_from_history,
    season_year, schedule_url,
)

TARGET = date(2026, 11, 17)


def event(game_id, date_utc, team_score, other_score, *,
          status="post", team_id="13"):
    return {
        "id": str(game_id), "date": date_utc,
        "status": {"type": {"state": status, "completed": status == "post"}},
        "competitions": [{"competitors": [
            {"team": {"id": team_id, "displayName": "Lakers"},
             "homeAway": "home", "score": {"value": team_score}},
            {"team": {"id": "9", "displayName": "Warriors"},
             "homeAway": "away", "score": other_score},
        ]}],
    }


class TeamFormTests(TestCase):
    def test_season_identity_and_url_validation(self):
        self.assertEqual(season_year("NBA", TARGET), 2027)
        self.assertEqual(season_year("NFL", TARGET), 2026)
        self.assertEqual(season_year("NHL", TARGET), 2027)
        self.assertIn("/hockey/nhl/", schedule_url("NHL", "13", TARGET))
        self.assertEqual(season_year("NFL", date(2027, 1, 10)), 2026)
        self.assertIn("season=2027", schedule_url("NBA", "13", TARGET))
        with self.assertRaises(ValueError):
            schedule_url("NBA", "../../13", TARGET)

    def test_excludes_game_today_future_and_in_progress(self):
        events = [
            event("1", "2026-11-12T02:00:00Z", "111", "105"),
            event("2", "2026-11-18T02:00:00Z", "115", "100"),
            event("3", "2026-11-14T02:00:00Z", "118", "117", status="in"),
            event("4", "2026-11-16T02:00:00Z", "120", "109"),
            event("4", "2026-11-16T02:00:00Z", "120", "109"),
        ]
        rows = completed_team_games({"events": events}, "NBA", "13", TARGET)
        self.assertEqual([r["event_id"] for r in rows], ["4", "1"])
        self.assertEqual([r["points_for"] for r in rows], [120.0, 111.0])
        self.assertTrue(rows[0]["home"])
        self.assertEqual(rows[0]["result"], "W")

    def test_espn_team_schedule_nested_status(self):
        example = event("17", "2026-11-14T02:00:00Z", 127, 105)
        example["competitions"][0]["status"] = example.pop("status")
        result = completed_team_games({"events": [example]}, "NBA", "13", TARGET)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["points_for"], 127.0)

    def test_invalid_scores_or_wrong_team_are_ignored(self):
        payload = {"events": [
            event("1", "2026-11-12T02:00:00Z", "DNP", "105"),
            event("2", "2026-11-13T02:00:00Z", "-2", "100"),
            event("3", "2026-11-14T02:00:00Z", "105", "100", team_id="11"),
        ]}
        self.assertEqual(completed_team_games(payload, "NBA", "13", TARGET), [])

    def test_forms_and_transparent_estimates(self):
        sample = [{
            "points_for": n, "points_against": 125 - n,
            "result": "W" if n > 62 else "L",
        } for n in [100, 106, 104, 110, 109, 98]]
        away = recent_team_form(sample)
        home = recent_team_form([dict(x, points_for=x["points_for"] + 6,
                                      points_against=x["points_against"] + 3)
                                 for x in sample])
        self.assertEqual(away["partidos"], 6)
        self.assertEqual(away["puntos_anotados_media"], 104.5)
        self.assertIsNotNone(away["desviacion_anotados"])
        params = scenario_from_forms("NBA", away, home, total_line=221.5)
        self.assertEqual(params["simulations"], 10000)
        self.assertEqual(params["score_correlation"], 0.0)
        self.assertEqual(params["away_mean"],
                         round((away["puntos_anotados_media"] +
                                home["puntos_recibidos_media"]) / 2, 2))
        self.assertEqual(params["status"], "ESCENARIO_DE_DESCRIPCION_HISTORICA_NO_VALIDADO")
        with self.assertRaises(ValueError):
            scenario_from_forms("NHL", away, home, total_line=5.5)


    def test_history_simulation_filters_future_results_and_uses_venue(self):
        before = TARGET
        rows = []
        for i in range(10):
            rows.append({
                "event_id": str(800+i), "date": (before-timedelta(days=i+1)).isoformat(),
                "points_for": 108+i%4, "points_against": 102+i%2,
                "home": i%2==0, "result": "W", "opponent": "Other",
            })
        # an impossible future event cannot contaminate the simulation
        future = {"event_id": "9999", "date": (before+timedelta(days=1)).isoformat(),
                  "points_for": 290, "points_against": 0, "home": True}
        base = scenario_from_history("NBA", rows, rows, before=before, total_line=220.5)
        leak = scenario_from_history(
            "NBA", [future]+rows, [future]+rows,
            before=before, total_line=220.5,
        )
        self.assertEqual(base, leak)
        self.assertEqual(base["away_count"], 10)
        self.assertEqual(base["home_count"], 10)
        self.assertIn("localía", base["method"])
        self.assertGreater(base["away_sd"], 0)
        self.assertEqual(base["score_correlation"], 0.0)
        self.assertEqual(base["status"], "HISTORICO_ESPN_PREPARTIDO_NO_CALIBRADO")

    def test_history_simulation_refuses_insufficient_samples(self):
        rows = [{
            "event_id": str(i), "date": (TARGET-timedelta(days=i+1)).isoformat(),
            "points_for": 100+i, "points_against": 90, "home": False,
        } for i in range(5)]
        with self.assertRaisesRegex(ValueError, "seis"):
            scenario_from_history("NBA", rows, rows, before=TARGET, total_line=220.5)

    def test_small_sample_rejected(self):
        self.assertIsNone(recent_team_form([
            {"points_for": 12, "points_against": 20, "result": "L"},
        ]))
