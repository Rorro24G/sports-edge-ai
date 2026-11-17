"""Asistente: los aciertos observados de Covers son auditables, no bank real."""
from datetime import datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from src.assistant_core import answer_query

NOW = datetime(2026, 11, 17, 12, 15, tzinfo=ZoneInfo("America/Mexico_City"))


def audit():
    return {
        "fecha_cdmx": "2026-11-17",
        "unidades_simuladas": 2,
        "grades": {
            "1": {
                "id": "1", "fecha": "2026-11-16", "resultado": "ganado",
                "beneficio_unidad": "0.80",
                "fuente_espn_resultado": "https://www.espn.com/nba/game/_/gameId/111",
            },
            "2": {
                "id": "2", "fecha": "2026-11-15", "resultado": "perdido",
                "beneficio_unidad": "-1.00",
                "fuente_espn_resultado": "https://www.espn.com/nhl/game/_/gameId/222",
            },
        },
    }


def chat(query, report=None):
    return answer_query(
        query, now=NOW, backtest_loader=lambda _: report,
        report_loader=lambda _: None,
        # Any wrong routing to ESPN must fail in these tests.
        board_fetch=lambda *a: (_ for _ in ()).throw(
            AssertionError("No se esperaba consulta ESPN adicional")),
        covers_fetch=lambda *a: (_ for _ in ()).throw(
            AssertionError("No se esperaba consulta Covers adicional")),
    )


class BacktestAssistantTests(TestCase):
    def test_answer_how_many_covers_picks_won(self):
        reply = chat("¿Qué porcentaje de picks de Covers acertaron?", audit())
        self.assertIn("2 encuentros", reply["reply"])
        self.assertIn("Ganadas 1", reply["reply"])
        self.assertIn("perdidas 1", reply["reply"])
        self.assertIn("50.0%", reply["reply"])
        self.assertIn("-0.20 unidades", reply["reply"])
        self.assertIn("-10.0%", reply["reply"])
        self.assertIn("NO son apuestas", reply["reply"])
        self.assertEqual(len(reply["sources"]), 2)

    def test_specific_date_not_global_success(self):
        r = chat("¿Cuántos picks Covers pegaron ayer?", audit())
        self.assertIn("1 encuentros", r["reply"])
        self.assertIn("100.0%", r["reply"])
        self.assertNotIn("-10.0%", r["reply"])
        # No matches today, so never reuse global historical accuracy.
        no = chat("¿Cuál es el rendimiento de picks Covers hoy?", audit())
        self.assertIn("No hay referencias", no["reply"])

    def test_missing_audit_no_claimed_results(self):
        r = chat("¿Cuál es el ROI de picks de Covers?", None)
        self.assertIn("Aún no tengo", r["reply"])

    def test_private_bank_remains_protected(self):
        r = chat("¿Cuánto tengo en mi bank?", audit())
        self.assertIn("Mi historial", r["reply"])
        self.assertNotIn("50.0%", r["reply"])
