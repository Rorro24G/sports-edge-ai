"""Independent picks must never use Covers projections to choose a winner."""
from datetime import date, datetime, timedelta
from unittest import TestCase
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.independent_picks import (
    VERSION, predict_from_results, evaluate_game, add_covers_price, build_slate
)
from src.team_form import season_year, completed_team_games, schedule_url

DAY = date(2026, 11, 17)
NOW = datetime(2026, 11, 17, 9, tzinfo=ZoneInfo("America/Mexico_City"))
GAME = {
    "sport": "NBA", "away": "Toronto Raptors", "home": "Philadelphia 76ers",
    "away_team_id": "28", "home_team_id": "20", "event_id": "401123456",
    "local_time": "18:00", "status": "SCHEDULED",
    "source_url": "https://www.espn.com/nba/game",
}
# Covers favors the opposite team; the engine should still choose Toronto.
COVERS = {
    "liga": "NBA", "partido": "Toronto @ Philadelphia",
    "fecha_cdmx": DAY.isoformat(), "hora_cdmx": "18:00",
    "proyeccion_visitante": 105.0, "proyeccion_local": 124.0,
    "momio_visitante": "+210", "momio_local": "-250",
    "fuente": "https://www.covers.com/picks/nba",
}


def schedule(for_points, against_points, n=10, *,
             add_future=False, n_future=2):
    rows = []
    for i in range(n):
        day = DAY - timedelta(days=i + 1)
        rows.append({
            "event_id": str(5000 + i),
            "date": day.isoformat(),
            "points_for": for_points + (i % 3),
            "points_against": against_points + (i % 2),
        })
    if add_future:
        for i in range(n_future):
            rows.append({
                "event_id": str(9000+i), "date": (DAY+timedelta(days=1+i)).isoformat(),
                "points_for": 0, "points_against": 299,
            })
    return {"games": rows, "source_url": "https://www.espn.com/nba/team/schedule"}


def fetch(team_sport, team_id, target):
    assert target == DAY
    if team_sport == "NBA":
        return schedule(122, 99) if team_id == "28" else schedule(95, 119)
    if team_sport == "NHL":
        return schedule(5.1, 2.0) if team_id == "28" else schedule(1.5, 4.8)
    raise AssertionError("Unexpected sport")


class OwnPicksTests(TestCase):
    def test_own_pick_disagrees_with_covers_and_keeps_market_prices(self):
        analysis = evaluate_game(GAME, DAY, team_fetch=fetch, now=NOW)
        self.assertEqual(analysis["status"], "CANDIDATO_EXPERIMENTAL")
        self.assertEqual(analysis["team"], "Toronto Raptors")
        self.assertEqual(analysis["side"], "visitante")
        self.assertEqual(analysis["stake"], 0)
        self.assertFalse(analysis["model_validated"])
        priced = add_covers_price(analysis, GAME, [COVERS], DAY)
        self.assertEqual(priced["market_price"], "+210")
        self.assertEqual(analysis["team"], priced["team"])
        self.assertEqual(priced["version"], VERSION)

    def test_price_projections_and_moneyline_never_change_the_choice(self):
        a = evaluate_game(GAME, DAY, team_fetch=fetch, now=NOW)
        changed = dict(COVERS, proyeccion_visitante=160, proyeccion_local=55,
                       momio_visitante="-700", momio_local="+450")
        x = add_covers_price(a, GAME, [COVERS], DAY)
        y = add_covers_price(a, GAME, [changed], DAY)
        self.assertEqual(x["team"], y["team"])
        self.assertEqual(x["probability_experimental"], y["probability_experimental"])
        self.assertNotEqual(x["market_price"], y["market_price"])

    def test_no_history_no_pick_even_with_favorite_market(self):
        missing = lambda *_: {"games": []}
        analysis = evaluate_game(GAME, DAY, team_fetch=missing, now=NOW)
        self.assertEqual(analysis["status"], "SIN_DATOS")
        self.assertNotIn("team", analysis)
        self.assertIsNone(add_covers_price(analysis, GAME, [COVERS], DAY)["market_price"])

    def test_future_results_do_not_contaminate_signal(self):
        normal = predict_from_results("NBA", "Away", "Home",
                                      schedule(122, 99), schedule(95, 119), DAY)
        leaked = predict_from_results("NBA", "Away", "Home",
                                      schedule(122, 99, add_future=True),
                                      schedule(95, 119, add_future=True), DAY)
        self.assertEqual(normal, leaked)

    def test_model_can_pass_tossup(self):
        result = predict_from_results("NBA", "Away", "Home",
                                      schedule(108, 110), schedule(108, 110), DAY)
        self.assertEqual(result["status"], "PASAR")
        self.assertEqual(result["stake"], 0)

    def test_ended_and_started_are_never_actionable(self):
        gone = dict(GAME, status="POST")
        self.assertEqual(evaluate_game(gone, DAY, team_fetch=fetch, now=NOW)["status"],
                         "NO_ANALIZABLE")
        older = dict(GAME, local_time="08:30")
        self.assertEqual(evaluate_game(older, DAY, team_fetch=fetch, now=NOW)["status"],
                         "NO_ANALIZABLE")

    def test_slate_has_own_candidates_and_no_market_dependency(self):
        empty = build_slate({"NBA": [GAME]}, DAY, team_fetch=fetch, now=NOW)
        quoted = build_slate({"NBA": [GAME]}, DAY, team_fetch=fetch,
                             covers_events=[COVERS], now=NOW)
        self.assertEqual(len(quoted["picks"]), 1)
        self.assertEqual(empty["picks"][0]["team"], quoted["picks"][0]["team"])
        self.assertIsNone(empty["picks"][0]["market_price"])
        self.assertEqual(quoted["picks"][0]["market_price"], "+210")
        self.assertEqual(quoted["eligible_games"], 1)

    def test_nhl_history_supported(self):
        self.assertEqual(season_year("NHL", DAY), 2027)
        self.assertIn("/hockey/nhl/", schedule_url("NHL", "28", DAY))
        nhl = dict(GAME, sport="NHL", away="Montreal Canadiens",
                   home="Boston Bruins")
        result = evaluate_game(nhl, DAY, team_fetch=fetch, now=NOW)
        self.assertEqual(result["status"], "CANDIDATO_EXPERIMENTAL")
        self.assertEqual(result["team"], "Montreal Canadiens")

    def test_does_not_rank_cross_sport_uncalibrated_probabilities(self):
        nhl = dict(GAME, sport="NHL", event_id="990",
                   away="Montreal Canadiens", home="Boston Bruins")
        def predict_fixture(game, target, **kwargs):
            return {
                "sport": game["sport"], "event_id": game["event_id"],
                "status": "CANDIDATO_EXPERIMENTAL",
                "side": "local", "team": game["home"], "stability": 1.0,
                "probability_experimental": (.95 if game["sport"] == "NHL" else .59),
                "margin_experimental": 2.0, "time": "18:00",
            }
        with patch("src.independent_picks.evaluate_game", side_effect=predict_fixture):
            slate = build_slate(
                {"NBA": [GAME], "NHL": [nhl]}, DAY,
                team_fetch=fetch, now=NOW,
            )
        self.assertEqual([row["sport"] for row in slate["picks"]],
                         ["NBA", "NHL"])

    def test_asof_excludes_same_day_final(self):
        from src.independent_picks import _history
        recent = schedule(120, 100)
        recent["games"].append({"event_id": "98765", "date": DAY.isoformat(),
                                "points_for": 200, "points_against": 3})
        rows = _history(recent, DAY, 10)
        self.assertEqual(len(rows), 10)
        self.assertNotIn("98765", [r["event_id"] for r in rows])
