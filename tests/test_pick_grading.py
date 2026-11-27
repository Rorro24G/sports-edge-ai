from datetime import date
from unittest import TestCase
from src.pick_grading import propose_moneyline_results

BASE = {
    "sport":"NBA", "event":"Lakers vs Warriors", "event_date_cdmx":"2026-11-17",
    "selection":"Lakers ML", "status":"pendiente", "id":"b1",
}
MATCH = {
    "sport":"NBA", "away":"Los Angeles Lakers", "home":"Golden State Warriors",
    "local_date":date(2026, 11, 17), "status":"POST",
    "away_score":"115", "home_score":"103",
    "source_url":"https://www.espn.com/nba/game",
}


class GradingTests(TestCase):
    def test_suggest_correct_moneyline_result(self):
        suggestions = propose_moneyline_results([BASE], [MATCH])
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["status"], "ganado")
        self.assertEqual(suggestions[0]["bet_id"], "b1")

    def test_suggest_loss(self):
        lost = dict(BASE, selection="Warriors ML")
        self.assertEqual(propose_moneyline_results([lost], [MATCH])[0]["status"], "perdido")

    def test_no_premature_or_ambiguous_grade(self):
        self.assertEqual(propose_moneyline_results([BASE], [dict(MATCH, status="IN")]), [])
        self.assertEqual(propose_moneyline_results([BASE], [dict(MATCH, away_score=None)]), [])
        self.assertEqual(propose_moneyline_results([BASE], [MATCH, MATCH]), [])
        self.assertEqual(propose_moneyline_results([BASE], [dict(MATCH, local_date=date(2026, 11, 16))]), [])
        self.assertEqual(propose_moneyline_results([dict(BASE, selection="Lakers +5.5")], [MATCH]), [])
        self.assertEqual(propose_moneyline_results([dict(BASE, status="ganado")], [MATCH]), [])
