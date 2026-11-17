"""Covers-derived selection tests, no fabricated model or pregame signals."""
from datetime import datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from src.pick_reference import covers_projection, visible_projections
from src.brain_dashboard import morning_covers_picks

MX = ZoneInfo("America/Mexico_City")
NOW = datetime(2026, 11, 17, 10, 30, tzinfo=MX)
EVENT = {
    "liga": "NBA", "partido": "Charlotte @ L.A. Lakers",
    "fecha_cdmx": "2026-11-17", "hora_cdmx": "22:00",
    "proyeccion_visitante": 106.03, "proyeccion_local": 116.49,
    "momio_visitante": "+260", "momio_local": "-300",
    "fuente": "https://www.covers.com/picks/nba",
}


def report_with(event):
    return {
        "date_cdmx": "2026-11-17",
        "leagues": {
            "NBA": {"events": [event]},
            "NHL": {"events": []},
            "NFL": {"events": []},
        },
    }


def report_event(**overrides):
    result = {
        "liga": "NBA", "partido": EVENT["partido"],
        "fecha_cdmx": "2026-11-17", "hora_cdmx": "22:00",
        "fuente_covers": EVENT["fuente"],
        "proyeccion_covers": [106.03, 116.49],
        "momios_covers": ["+260", "-300"],
    }
    result.update(overrides)
    return result


class CoversSelectionsTests(TestCase):
    def test_explicit_pick_and_price_references(self):
        pick = covers_projection(EVENT, now=NOW)
        self.assertEqual(pick["seleccion_de_referencia"], "L.A. Lakers ML")
        self.assertEqual(pick["momio_covers"], "-300")
        self.assertEqual(pick["umbral_equilibrio_precio"], 75.0)
        self.assertEqual(pick["total_proyectado"], 222.52)
        self.assertEqual(pick["margen_proyectado"], 10.46)
        self.assertTrue(pick["vigente_para_analisis_prepartido"])
        self.assertIsNone(pick["probabilidad_propia"])
        self.assertIsNone(pick["ev_propio"])
        self.assertIsNone(pick["stake_recomendado"])
        self.assertFalse(pick["pick_validado"])

    def test_past_game_is_not_actionable(self):
        self.assertFalse(covers_projection(EVENT, now=datetime(
            2026, 11, 17, 22, 1, tzinfo=MX
        ))["vigente_para_analisis_prepartido"])
        self.assertEqual(visible_projections([EVENT], now=datetime(
            2026, 11, 17, 22, 1, tzinfo=MX
        )), [])

    def test_tie_or_invalid_score_prevents_selection(self):
        self.assertIsNone(covers_projection(dict(
            EVENT, proyeccion_visitante=110, proyeccion_local=110,
        ), now=NOW))
        self.assertIsNone(covers_projection(dict(
            EVENT, proyeccion_visitante="54%", proyeccion_local=110,
        ), now=NOW))

    def test_fake_percent_not_a_moneyline(self):
        signal = covers_projection(dict(EVENT, momio_local="75%"), now=NOW)
        self.assertIsNone(signal["momio_covers"])
        self.assertIsNone(signal["umbral_equilibrio_precio"])

    def test_morning_picks_require_covers_source_and_price(self):
        valid = report_event()
        rows = morning_covers_picks(report_with(valid), now=NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Referencia ML (Covers)"], "L.A. Lakers ML")
        self.assertEqual(rows[0]["Momio publicado"], "-300")
        self.assertEqual(rows[0]["Fuente"], EVENT["fuente"])
        self.assertEqual(morning_covers_picks(report_with(
            report_event(fuente_covers=None)
        ), now=NOW), [])
        self.assertEqual(morning_covers_picks(report_with(
            report_event(momios_covers=["+260", None])
        ), now=NOW), [])

    def test_morning_report_no_future_or_wrong_day(self):
        self.assertEqual(morning_covers_picks(
            report_with(report_event()), now=datetime(2026, 11, 18, 10, tzinfo=MX)
        ), [])
        self.assertEqual(morning_covers_picks(
            report_with(report_event()), now=datetime(2026, 11, 17, 22, 10, tzinfo=MX)
        ), [])

    def test_morning_only_top_three_per_league_not_fake_win_rate(self):
        events = [
            report_event(partido=f"Charlotte @ {name}", hora_cdmx="22:00",
                         proyeccion_covers=[106, score])
            for name, score in [("Los Angeles", 108), ("Boston", 120),
                                ("New York", 110), ("Miami", 113)]
        ]
        report = {"date_cdmx": "2026-11-17", "leagues": {
            "NBA": {"events": events}, "NFL": {"events": []}, "NHL": {"events": []}
        }}
        rows = morning_covers_picks(report, now=NOW)
        self.assertEqual(len(rows), 3)
        self.assertEqual([x["Diferencia de marcador"] for x in rows], [14, 7, 4])
        self.assertTrue(all("EV" not in x and "Probabilidad propia" not in x for x in rows))
