"""Tests offline del asistente natural sin inventar mercados ni apuestas."""
from datetime import date, datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from src.assistant_core import answer_query, _trusted_sources

MX = ZoneInfo("America/Mexico_City")
NOW = datetime(2026, 11, 17, 9, 0, tzinfo=MX)


def board(league, target):
    if league != "NBA":
        return {"games": [], "url": ""}
    return {"games": [{
        "sport": "NBA", "away": "Golden State Warriors",
        "home": "Los Angeles Lakers",
        "away_team_id": "9", "home_team_id": "13",
        "status": "SCHEDULED", "local_time": "23:00",
        "source_url": "https://www.espn.com/nba/game",
        "event_id": "401234567",
    }], "url": "https://www.espn.com/nba/scoreboard"}


def covers(league, target):
    if league != "NBA":
        return {"events": []}
    return {"events": [{
        "liga": "NBA", "partido": "Golden State @ L.A. Lakers",
        "fecha_cdmx": "2026-11-17", "hora_cdmx": "23:00",
        "proyeccion_visitante": 105, "proyeccion_local": 115,
        "momio_visitante": "+125", "momio_local": "-145",
        "spreads_publicados": "-4.5 -110",
        "totales_publicados": "o219.5 -110",
        "fuente": "https://www.covers.com/picks/nba",
    }]}


def roster(team):
    return {"athletes": ([{"id": "3945274", "name": "Luka Doncic",
                           "team_id": "13", "injuries": [], "status": "Active"}]
                         if team == "13" else [])}


def log(player_id, target):
    return {"payload": {
        "labels": ["MIN", "REB", "AST", "PTS"],
        "events": {
            "101": {"gameDate": "2026-11-10T02:00Z",
                    "opponent": {"abbreviation": "BOS"}},
            "102": {"gameDate": "2026-11-12T02:00Z",
                    "opponent": {"abbreviation": "NYK"}},
        },
        "seasonTypes": [{"id": "2", "displayName": "Regular Season",
                         "categories": [{"events": [
                             {"eventId": "101", "stats": ["34", "5", "8", "25"]},
                             {"eventId": "102", "stats": ["36", "6", "9", "32"]},
                         ]}]}],
    }, "checked_at_utc": "2026-11-17T13:00:00Z"}


def snapshot():
    sections = {}
    for league, matches in {
        "NBA": ["Golden State @ L.A. Lakers", "Detroit @ San Antonio",
                "Utah @ Philadelphia", "Charlotte @ Boston"],
        "NHL": ["Edmonton @ Florida", "Toronto @ Montreal", "Calgary @ Tampa Bay"],
        "NFL": [],
    }.items():
        sections[league] = {"events": [{
            "liga": league, "partido": match,
            "fecha_cdmx": "2026-11-17", "hora_cdmx": "23:00",
            "proyeccion_covers": [100, 110] if league == "NBA" else [2, 3],
            "momios_covers": ["+115", "-130"],
            "espn": {"evento": str(i + 401001)},
            "fuente_covers": "https://www.covers.com/picks/" + league.lower(),
        } for i, match in enumerate(matches)]}
    return {"date_cdmx": "2026-11-17", "leagues": sections}


def assistant(text, *, context=None, report=None):
    return answer_query(
        text, context=context, now=NOW, board_fetch=board,
        covers_fetch=covers, roster_fetch=roster,
        gamelog_fetch=log, report_loader=lambda _: report,
    )


class AssistantTests(TestCase):
    def test_props_by_name_and_followup_line(self):
        a = assistant("Over de 24,5 puntos de Luka Doncic NBA hoy")
        self.assertIn("Luka Doncic", a["reply"])
        self.assertIn("Over 24.5 puntos", a["reply"])
        self.assertIn("2 aciertos", a["reply"])
        self.assertIn("NO probabilidad", a["reply"])
        self.assertEqual(a["context"]["player_name"], "Luka Doncic")
        b = assistant("¿y el under de 30,5?", context=a["context"])
        self.assertIn("Under 30.5 puntos", b["reply"])
        self.assertIn("1 aciertos", b["reply"])
        self.assertIn("Luka Doncic", b["reply"])
        self.assertEqual(b["context"]["player_stat"], "PTS")

    def test_moneyline_matchup_without_guessing_wrong_game(self):
        r = assistant("Analiza Lakers contra Warriors NBA hoy")
        self.assertIn("Golden State @ L.A. Lakers", r["reply"])
        self.assertIn("-145", r["reply"])
        self.assertIn("NO un pick propio", r["reply"])
        later = assistant("¿Y el total de ese partido?", context=r["context"])
        self.assertIn("o219.5 -110", later["reply"])
        other = assistant("Dame Miami vs Toronto NBA hoy")
        self.assertIn("No encontré un partido inequívoco", other["reply"])
        self.assertNotIn("Golden State @ L.A. Lakers", other["reply"])

    def test_picks_from_today_not_old_report(self):
        r = assistant("Picks NBA hoy", report=snapshot())
        self.assertIn("Referencias prepartido de Covers", r["reply"])
        self.assertIn("Precio", r["reply"].replace("Precios", "Precio"))
        self.assertIn("NO por probabilidad", r["reply"])
        self.assertTrue(r["sources"])
        empty = assistant("Picks NHL mañana", report=snapshot())
        self.assertNotIn("Referencias prepartido", empty["reply"])

    def test_parlay_borradores_and_no_probs(self):
        r = assistant("Dame 3 parlays de 2 selecciones hoy", report=snapshot())
        self.assertIn("Alternativa 1", r["reply"])
        self.assertIn("Alternativa 2", r["reply"])
        self.assertIn("cuota combinada", r["reply"])
        self.assertNotIn("probabilidad conjunta: 70%", r["reply"])
        self.assertTrue(r["sources"])

    def test_bank_not_accessible_without_login(self):
        r = assistant("¿Cuánto tengo de bank y cómo registro?")
        self.assertIn("Mi historial", r["reply"])
        self.assertIn("No tengo acceso a tu saldo", r["reply"])
        self.assertEqual(r["sources"], [])

    def test_reject_malicious_urls_and_oversized_message(self):
        self.assertEqual(_trusted_sources([
            "https://example.com/hacked", "http://www.espn.com/",
            "https://www.covers.com/picks/nba",
            "https://www.covers.com/picks/nba",
        ]), ["https://www.covers.com/picks/nba"])
        huge = assistant("Lakers " * 350)
        self.assertIn("demasiado larga", huge["reply"])
        self.assertEqual(huge["sources"], [])

    def test_unsupported_props_are_not_basketball_data(self):
        r = assistant("Under 45 puntos de jugador NHL hoy")
        self.assertIn("para NBA", r["reply"])
