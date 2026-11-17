"""Pruebas sin red del informe de mañana, sin picks ni cuotas inventadas."""
from datetime import date
from unittest import TestCase
from src.daily_picks import build_report, render_markdown

DAY = date(2026, 11, 17)


def covers(league, day):
    events = []
    if league == "NBA":
        events = [{
            "liga": "NBA", "partido": "Toronto @ Philadelphia",
            "fecha_cdmx": day.isoformat(), "hora_cdmx": "18:00",
            "fuente": "https://www.covers.com/picks/nba",
            "proyeccion_visitante": 106, "proyeccion_local": 112,
            "momio_visitante": "+150", "momio_local": "-180",
            "spreads_publicados": "+4.5 -110",
            "totales_publicados": "o218.5 -110",
            "probabilidades_publicadas": None,
        }]
    return {"events": events}


def board(league, day):
    if league != "NBA":
        return {"games": []}
    return {"games": [{
        "sport": "NBA", "away": "Toronto Raptors", "home": "Philadelphia 76ers",
        "event_id": "401234567", "local_time": "18:00", "status": "pre",
        "source_url": "https://www.espn.com/nba/game",
    }]}


def summary(league, event_id):
    return {"injuries": [{"Jugador": "Ejemplo", "Estado ESPN": "Out"}],
            "leaders": [], "news": [], "checked_at_utc": "2026-11-17T12:00:00+00:00"}


class DailyPicksTests(TestCase):
    def test_report_has_source_and_never_claims_value(self):
        report = build_report(DAY, covers_fetch=covers, board_fetch=board,
                              summary_fetch=summary)
        game = report["leagues"]["NBA"]["events"][0]
        self.assertEqual(len(report["leagues"]["NBA"]["events"]), 1)
        self.assertEqual(game["momios_covers"], ["+150", "-180"])
        self.assertEqual(game["probabilidad_implicita_mercado"]["visitante"], 40.0)
        self.assertIsNone(game["pick_propio"])
        self.assertEqual(game["espn"]["lesiones"][0]["Estado ESPN"], "Out")
        self.assertEqual(game["momios_casas"], [])
        self.assertIn("SIN MODELO VALIDADO", render_markdown(report))

    def test_no_schedule_is_not_false_prediction(self):
        report = build_report(DAY, covers_fetch=lambda *a: {"events": []},
                              board_fetch=lambda *a: {"games": []},
                              summary_fetch=summary)
        self.assertEqual(report["leagues"]["NBA"]["events"], [])
        self.assertEqual(report["pick_status"], "SIN_MODELO_VALIDADO")

    def test_espn_calendar_survives_covers_failure(self):
        from src.covers_public import CoversSourceError

        def fails(*args):
            raise CoversSourceError("HTTP 403")

        report = build_report(DAY, covers_fetch=fails, board_fetch=board,
                              summary_fetch=summary)
        nba = report["leagues"]["NBA"]
        self.assertEqual(nba["coverage"]["covers"], "error")
        self.assertEqual(len(nba["events"]), 1)
        self.assertEqual(nba["events"][0]["datos_covers"],
                         "no_verificados_para_este_partido")
        self.assertIsNone(nba["events"][0]["pick_propio"])

    def test_optional_api_only_if_key_supplied(self):
        calls = []

        def external(*args):
            calls.append(args)
            return []

        build_report(DAY, covers_fetch=covers, board_fetch=board,
                     summary_fetch=summary, odds_fetch=external)
        self.assertEqual(calls, [])
        build_report(DAY, covers_fetch=covers, board_fetch=board,
                     summary_fetch=summary, odds_fetch=external,
                     odds_key="dummy-value")
        self.assertEqual(len(calls), 3)
