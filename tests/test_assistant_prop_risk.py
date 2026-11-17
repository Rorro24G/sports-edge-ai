"""El bot une riesgos, lesiones y cotización exacta; sin inventar EV."""
from datetime import date, datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from src.assistant_core import answer_query

NOW = datetime(2026, 11, 17, 9, 0, tzinfo=ZoneInfo("America/Mexico_City"))
GAME = {
    "sport": "NBA", "away": "Golden State Warriors", "home": "Los Angeles Lakers",
    "away_team_id": "9", "home_team_id": "13", "local_date": date(2026, 11, 17),
    "local_time": "22:00", "event_id": "401234567", "status": "SCHEDULED",
}

def board(league, target):
    assert league == "NBA"
    return {"games": [GAME], "url": "https://www.espn.com/nba/scoreboard"}

def roster(team):
    return {"athletes": [{
        "id": "3945274", "name": "Luka Doncic", "team_id": "13",
        "status": "Questionable",
        "injuries": [{"status": "Questionable"}],
    }] if team == "13" else []}

def log(player_id, target):
    return {"payload": {
        "labels": ["MIN", "PTS"],
        "events": {
            "101": {"gameDate": "2026-11-10T02:00Z",
                    "opponent": {"abbreviation": "BOS"}},
            "102": {"gameDate": "2026-11-12T02:00Z",
                    "opponent": {"abbreviation": "NYK"}},
        },
        "seasonTypes": [{"id": "2", "displayName": "Regular Season",
                         "categories": [{"events": [
                             {"eventId": "101", "stats": ["34", "25"]},
                             {"eventId": "102", "stats": ["36", "32"]},
                         ]}]}],
    }, "checked_at_utc": "2026-11-17T13:00:00Z"}

def fetch_quote(api_key, game, target, player_name, stat, direction, line):
    assert api_key == "offline-fixture-only"
    assert game["event_id"] == "401234567"
    assert player_name == "Luka Doncic"
    assert (stat, direction, line) == ("PTS", "over", 24.5)
    return [{
        "casa": "BetMGM", "momio_americano": -110,
        "actualizado_utc": "2026-11-17T13:00:00+00:00",
        "fuente": "The Odds API",
    }]


class AdvancedAssistantTests(TestCase):
    def test_player_quote_injury_and_limits_in_single_reply(self):
        result = answer_query(
            "Over de 24.5 puntos de Luka Doncic NBA hoy",
            now=NOW, board_fetch=board, roster_fetch=roster,
            gamelog_fetch=log, prop_odds_fetch=fetch_quote,
            prop_api_key="offline-fixture-only",
        )
        self.assertIn("Luka Doncic", result["reply"])
        self.assertIn("BetMGM -110", result["reply"])
        self.assertIn("lesión", result["reply"])
        self.assertIn("Muestra inferior", result["reply"])
        self.assertIn("NO probabilidad predictiva", result["reply"])
        self.assertNotIn("EV +", result["reply"])
        self.assertIn("espn.com", " ".join(result["sources"]))

    def test_without_key_never_fetch_quotes(self):
        result = answer_query(
            "Over de 24.5 puntos de Luka Doncic NBA hoy",
            now=NOW, board_fetch=board, roster_fetch=roster,
            gamelog_fetch=log,
            prop_odds_fetch=lambda *a: (_ for _ in ()).throw(
                AssertionError("No debe llamar la API sin clave")),
        )
        self.assertNotIn("BetMGM", result["reply"])
        self.assertIn("Sin cotización", result["reply"])
        self.assertNotIn("ODDS_API_KEY", result["reply"])


    def test_injury_followup_refreshes_roster_and_retains_market(self):
        first = answer_query(
            "Over de 24.5 puntos de Luka Doncic NBA hoy", now=NOW,
            board_fetch=board, roster_fetch=roster, gamelog_fetch=log,
        )
        calls = []
        def updated(team):
            calls.append(team)
            result = roster(team)
            for player in result["athletes"]:
                player["status"] = "Out"
                player["injuries"] = [{"status": "Out"}]
            return result
        second = answer_query(
            "¿Y las lesiones?", context=first["context"], now=NOW,
            board_fetch=board, roster_fetch=updated, gamelog_fetch=log,
        )
        self.assertIn("13", calls)
        self.assertIn("Over 24.5 puntos", second["reply"])
        self.assertIn("Estado de plantilla ESPN: Out", second["reply"])
        self.assertIn("2026-11-17T13:00:00Z", second["reply"])

    def test_failed_refresh_does_not_reuse_old_availability(self):
        first = answer_query(
            "Over de 24.5 puntos de Luka Doncic NBA hoy", now=NOW,
            board_fetch=board, roster_fetch=roster, gamelog_fetch=log,
        )
        second = answer_query(
            "¿Y los riesgos?", context=first["context"], now=NOW,
            board_fetch=board, roster_fetch=lambda _: {"athletes": []},
            gamelog_fetch=lambda *a: self.fail("No usar historial sin identificar jugador"),
        )
        self.assertIn("No pude identificar", second["reply"])
        self.assertNotIn("Questionable", second["reply"])
