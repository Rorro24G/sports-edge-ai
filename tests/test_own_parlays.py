"""Own parlays must use ESPN model decisions and never Covers projected winners."""
from datetime import date, datetime, timedelta
from unittest import TestCase
from zoneinfo import ZoneInfo

from src.independent_picks import VERSION
from src.own_parlays import (
    build_own_parlays, own_parlay_review_prompt, _verified_url,
)

MX = ZoneInfo("America/Mexico_City")
DAY = date(2026, 11, 18)
NOW = datetime(2026, 11, 18, 9, 32, tzinfo=MX)


def pick(i, sport="NBA", *, price=None):
    away, home = f"Road Team {i}", f"Home Team {i}"
    return {
        "status": "CANDIDATO_EXPERIMENTAL",
        "sport": sport, "event_id": str(401800+i),
        "away": away, "home": home, "side": "visitante",
        "team": away, "time": "22:15",
        "version": VERSION, "model_validated": False,
        "probability_experimental": 0.60+i*.01,
        "stability": .8+i*.01,
        "reason": "ESPN: mejor forma y ataque visitante",
        "espn_url": f"https://www.espn.com/{sport.lower()}/game/_/gameId/{401800+i}",
        "market_price": price,
        "market_source": "https://www.covers.com/picks/nba" if price else None,
    }


def slate(picks):
    return {"model": VERSION, "picks": picks, "evaluated": picks,
            "eligible_games": len(picks)}


class OwnParlayTests(TestCase):
    def test_generates_three_real_alternatives_with_two_legs_even_without_covers(self):
        data = slate([pick(1), pick(2), pick(3), pick(4)])
        result = build_own_parlays(data, DAY, count=3, now=NOW)
        self.assertEqual(result["available"], 4)
        self.assertEqual(len(result["proposals"]), 3)
        signatures = set()
        for proposal in result["proposals"]:
            self.assertEqual(proposal["tipo"], "BORRADOR_SEAI_EXPERIMENTAL")
            self.assertEqual(proposal["num_selecciones"], 2)
            self.assertIsNone(proposal["cuota_decimal_teorica"])
            self.assertIsNone(proposal["probabilidad_conjunta"])
            self.assertIsNone(proposal["ev_propio"])
            self.assertIsNone(proposal["stake_recomendado"])
            ids = [leg["espn_evento"] for leg in proposal["selecciones"]]
            self.assertEqual(len(ids), len(set(ids)))
            signatures.add(frozenset(ids))
            self.assertTrue(all(leg["momio_covers"] is None for leg in proposal["selecciones"]))
            draft = own_parlay_review_prompt(proposal)
            self.assertIn("elección propia:", draft)
            self.assertIn("Momio externo NO verificado.", draft)
            self.assertIn("No se calculó cuota", draft)
        self.assertEqual(len(signatures), 3)

    def test_optional_covers_price_never_changes_the_selected_side(self):
        original = slate([pick(1), pick(2)])
        first = build_own_parlays(original, DAY, now=NOW)["proposals"][0]
        changed = slate([pick(1, price="+150"), pick(2, price="-120")])
        other = build_own_parlays(changed, DAY, now=NOW)["proposals"][0]
        self.assertEqual(
            [leg["seleccion"] for leg in first["selecciones"]],
            [leg["seleccion"] for leg in other["selecciones"]],
        )
        self.assertIsNone(first["cuota_decimal_teorica"])
        self.assertEqual(other["cuota_decimal_teorica"], "4.58")
        self.assertIn("NO es una cuota real", own_parlay_review_prompt(other))

    def test_do_not_use_passes_or_started_games_to_fill_parlay(self):
        candidates = [pick(1)]
        candidates += [dict(pick(i), status="PASAR") for i in (2, 3)]
        candidates.append(dict(pick(4), time="08:00"))
        candidates.append(dict(pick(5), status="SIN_DATOS"))
        result = build_own_parlays(slate(candidates), DAY, now=NOW)
        self.assertEqual(result["available"], 1)
        self.assertEqual(result["proposals"], [])
        self.assertIn("al menos 2 partidos", result["reason"])
        self.assertIn("PASAR", result["excluded"])
        self.assertNotIn("CANDIDATO_EXPERIMENTAL", result["excluded"])

    def test_duplicate_game_cannot_appear_twice_or_create_fake_alternatives(self):
        rows = [pick(1), dict(pick(1)), pick(2)]
        result = build_own_parlays(slate(rows), DAY, now=NOW)
        self.assertEqual(result["available"], 2)
        self.assertEqual(len(result["proposals"]), 1)
        self.assertIn("Solo existen 1 combinaciones", result["reason"])

    def test_invalid_espn_source_never_becomes_a_leg(self):
        rows = [pick(1), pick(2)]
        rows[1]["espn_url"] = "https://espn.com.evil.example/fake"
        result = build_own_parlays(slate(rows), DAY, now=NOW)
        self.assertEqual(result["available"], 1)
        self.assertFalse(result["proposals"])
        self.assertIsNone(_verified_url("http://www.espn.com/game", "espn.com"))
        self.assertIsNone(_verified_url("https://name@www.espn.com/", "espn.com"))

    def test_slate_from_another_model_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "incompatible"):
            build_own_parlays(dict(slate([pick(1), pick(2)]), model="Covers"), DAY, now=NOW)
        with self.assertRaisesRegex(ValueError, "2 a 10"):
            build_own_parlays(slate([]), DAY, legs_per_parlay=1, now=NOW)
        with self.assertRaisesRegex(ValueError, "2 o 3"):
            build_own_parlays(slate([]), DAY, count=5, now=NOW)

    def test_expired_date_returns_no_old_tickets(self):
        report = build_own_parlays(slate([pick(1), pick(2)]),
                                   DAY-timedelta(days=1), now=NOW)
        self.assertEqual(report["proposals"], [])
        self.assertIn("hoy", report["reason"])

    def test_cross_sport_interleave_not_global_probability_ranking(self):
        result = build_own_parlays(slate([
            pick(1, "NBA"), pick(2, "NBA"),
            pick(3, "NHL"), pick(4, "NFL")
        ]), DAY, legs_per_parlay=3, now=NOW)
        self.assertEqual([leg["liga"] for leg in
                          result["proposals"][0]["selecciones"]],
                         ["NBA", "NFL", "NHL"])

    def test_partially_filled_three_leg_ticket_does_not_invent_third(self):
        result = build_own_parlays(
            slate([pick(1), pick(2)]), DAY, legs_per_parlay=3, now=NOW
        )
        self.assertEqual(len(result["proposals"]), 1)
        self.assertTrue(result["proposals"][0]["incompleto"])
        self.assertEqual(result["proposals"][0]["num_selecciones"], 2)

    def test_unsupported_more_than_ten_needs_explicit_permission(self):
        with self.assertRaisesRegex(ValueError, "2 a 10"):
            build_own_parlays(slate([]), DAY, legs_per_parlay=11, now=NOW)
        many = slate([pick(i) for i in range(12)])
        result = build_own_parlays(
            many, DAY, legs_per_parlay=11, more_than_ten=True, now=NOW
        )
        self.assertEqual(result["proposals"][0]["num_selecciones"], 11)
