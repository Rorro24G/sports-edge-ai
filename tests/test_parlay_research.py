"""Parlays: solo borradores documentados de Covers, no ganancias inventadas."""
from datetime import datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from src.parlay_research import (build_reference_parlays, candidate_legs,
                                 parlay_review_prompt)

MX = ZoneInfo("America/Mexico_City")
NOW = datetime(2026, 11, 17, 10, 0, tzinfo=MX)


def snapshot():
    rows = {}
    for league, names in {
        "NBA": ["Charlotte @ L.A. Lakers", "Detroit @ San Antonio",
                "Portland @ Minnesota", "Utah @ Los Angeles"],
        "NHL": ["Edmonton @ Florida", "Nashville @ Minnesota",
                "Dallas @ Vegas", "Toronto @ Chicago"],
        "NFL": ["New York @ Dallas", "Miami @ Buffalo"],
    }.items():
        rows[league] = {"events": [{
            "liga": league, "partido": name,
            "fecha_cdmx": "2026-11-17", "hora_cdmx": "21:00",
            "fuente_covers": "https://www.covers.com/picks/" + league.lower(),
            "momios_covers": ["+115", "-130"],
            "proyeccion_covers": ([107, 113] if league == "NBA"
                                  else [2.6, 3.2] if league == "NHL"
                                  else [22.0, 25.0]),
            "espn": {"evento": str(i + 401000), "fuente": "https://www.espn.com/"},
        } for i, name in enumerate(names)]}
    return {"date_cdmx": "2026-11-17", "leagues": rows}


class ParlayReferenceTests(TestCase):
    def test_three_drafts_are_distinct_and_have_sources(self):
        result = build_reference_parlays(snapshot(), count=3, legs_per_parlay=3, now=NOW)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(len(p["selecciones"]) == 3 for p in result))
        signatures = [
            frozenset((leg["liga"], leg["evento"]) for leg in p["selecciones"])
            for p in result
        ]
        self.assertEqual(len(set(signatures)), 3)
        for draft in result:
            self.assertEqual(draft["tipo"], "BORRADOR_PARLAY_NO_VALIDADO")
            self.assertIsNone(draft["probabilidad_conjunta"])
            self.assertIsNone(draft["ev_propio"])
            self.assertIsNone(draft["stake_recomendado"])
            self.assertIsNone(draft["cuota_real_ofrecida_por_casa"])
            self.assertTrue(all(leg["fuente"].startswith("https://www.covers.com/")
                                for leg in draft["selecciones"]))
            self.assertIn("NO es una cuota real", parlay_review_prompt(draft))

    def test_rejects_past_events_and_wrong_day(self):
        report = snapshot()
        self.assertEqual(build_reference_parlays(report, now=datetime(
            2026, 11, 17, 22, tzinfo=MX
        )), [])
        self.assertEqual(build_reference_parlays(report, now=datetime(
            2026, 11, 18, 9, tzinfo=MX
        )), [])

    def test_require_espn_match_and_covers_quote(self):
        report = snapshot()
        report["leagues"]["NBA"]["events"][0]["espn"] = None
        report["leagues"]["NBA"]["events"][1]["momios_covers"] = ["+115", None]
        report["leagues"]["NBA"]["events"][2]["fuente_covers"] = None
        result = candidate_legs(report, now=NOW)["NBA"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["evento"], "Utah @ Los Angeles")

    def test_no_more_than_ten_without_permission(self):
        with self.assertRaises(ValueError):
            build_reference_parlays(snapshot(), legs_per_parlay=11, now=NOW)
        result = build_reference_parlays(snapshot(), legs_per_parlay=11,
                                         more_than_ten=True, now=NOW)
        self.assertTrue(result)
        self.assertTrue(all(len(p["selecciones"]) <= 10 for p in result))
        self.assertTrue(all(p["num_selecciones"] == 10 for p in result))

    def test_one_selection_is_not_mislabeled_parlay(self):
        result = build_reference_parlays(snapshot(), legs_per_parlay=1, now=NOW)
        self.assertTrue(result)
        self.assertEqual(result[0]["tipo"], "APUESTA_SIMPLE_DE_REFERENCIA")

    def test_missing_sources_yields_no_fabricated_parlay(self):
        report = {"date_cdmx": "2026-11-17",
                  "leagues": {name: {"events": []} for name in ("NBA", "NHL", "NFL")}}
        self.assertEqual(build_reference_parlays(report, now=NOW), [])
        self.assertEqual(build_reference_parlays(snapshot(), count=2, now=NOW).__len__(), 2)

    def test_reject_duplicate_event_in_same_ticket(self):
        report = snapshot()
        duplicate = dict(report["leagues"]["NBA"]["events"][0])
        report["leagues"]["NBA"]["events"].append(duplicate)
        grouped = candidate_legs(report, now=NOW)
        self.assertEqual(len(grouped["NBA"]), 4)

    def test_theoretical_odds_not_bookmaker_offer(self):
        result = build_reference_parlays(snapshot(), count=2, legs_per_parlay=2,
                                         now=NOW)
        # -130 => decimal 1.76923 per leg; product ~3.13, never quoted as a
        # cashable combination from any real sportsbook.
        self.assertEqual(result[0]["cuota_decimal_teorica"], "3.13")
        self.assertIn("distintas casas", result[0]["restricciones"])
