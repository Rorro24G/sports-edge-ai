"""Full Streamlit test: real own NBA engine forms parlays, no Covers required."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest

NOW = datetime.now(ZoneInfo("America/Mexico_City"))
TODAY = NOW.date()


def scoreboard(league, day):
    fixtures = []
    if league == "NBA":
        for i in range(4):
            fixtures.append({
                "sport": "NBA",
                "away": "Road Stars " + str(i),
                "home": "Home Stars " + str(i),
                "event_id": str(40110000+i),
                "away_team_id": str(30+2*i),
                "home_team_id": str(31+2*i),
                "local_date": day.isoformat(),
                "local_time": "23:59", "status": "SCHEDULED",
                "source_url": "https://www.espn.com/nba/game/_/gameId/" + str(40110000+i),
            })
    return {"games": fixtures, "checked_at_utc": "2026-11-18T12:00:00Z"}


def team_history(sport, team_id, target):
    strong = int(team_id) % 2 == 0
    return {
        "games": [{
            "event_id": str(int(team_id)*1000+i),
            "date": (target - timedelta(days=i+1)).isoformat(),
            "points_for": (125 if strong else 92) + (i % 3),
            "points_against": (91 if strong else 124) + (i % 2),
            "home": bool(i%2),
        } for i in range(10)],
        "source_url": "https://www.espn.com/nba/team/schedule",
    }


with (
    patch("src.live_board.fetch_scoreboard", side_effect=scoreboard),
    patch("src.team_form.fetch_team_schedule", side_effect=team_history),
    patch("src.covers_public.fetch_public_picks",
          side_effect=AssertionError("Parlays must not need Covers")),
):
    app = AppTest.from_file("../app.py", default_timeout=50)
    app.session_state["brain_section"] = "parlays"
    app = app.run()
    assert not app.exception, [str(e.message) for e in app.exception]
    visible = "\n".join(str(x.value) for x in app.markdown)
    assert "Parlays propios del cerebro" in visible
    assert "Combinaciones generadas" in visible, "Own picks were not combined"
    assert "Parlay propio 1" in visible
    metrics = {m.label: str(m.value) for m in app.metric}
    assert metrics["Picks propios del cerebro"] == "4", metrics
    assert metrics["Combinaciones distintas"] == "3", metrics
    assert any(b.key == "discutir_parlay_0" for b in app.button)
    app = app.button(key="discutir_parlay_0").click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    draft = app.session_state["parlay_chat_question"]
    assert "elección propia:" in draft
    assert "Momio externo NO verificado" in draft
    assert "No se calculó cuota combinada" in draft
    assert "Fuente: https://www.espn.com/" in draft
    assert "no es una recomendación validada" in draft.lower()
    assert "NO es una cuota real ofrecida" not in draft
    print("STREAMLIT_OWN_PARLAYS_FROM_ESPN_OK")


# Verify the OPTIONAL price enrichment is joined after the model made its pick.
# A malformed Covers projection must not change the winner or produce a bet.
from src.parlay_ui import _enrich_prices
from src.independent_picks import VERSION

own_pick = {
    "status": "CANDIDATO_EXPERIMENTAL", "sport": "NBA",
    "event_id": "40110000", "away": "Road Stars 0", "home": "Home Stars 0",
    "time": "23:59", "team": "Road Stars 0", "side": "visitante",
    "version": VERSION, "model_validated": False, "stability": .9,
    "probability_experimental": .61,
    "espn_url": "https://www.espn.com/nba/game/_/gameId/40110000",
}

def quoted(sport, day):
    return {"events": [{
        "liga": "NBA", "partido": "Road Stars 0 @ Home Stars 0",
        "fecha_cdmx": day.isoformat(), "hora_cdmx": "23:59",
        "momio_visitante": "+115", "momio_local": "-125",
        "fuente": "https://www.covers.com/picks/nba",
        "proyeccion_visitante": 70, "proyeccion_local": 150,
    }] if sport == "NBA" else []}

enriched, errors = _enrich_prices({"model": VERSION, "picks": [own_pick]},
                                   TODAY, ["NBA"], quoted)
assert errors == []
assert enriched["picks"][0]["team"] == "Road Stars 0", "Covers changed the model winner"
assert enriched["picks"][0]["market_price"] == "+115", "Quoted moneyline did not join"
assert enriched["picks"][0]["market_source"] == "https://www.covers.com/picks/nba"
print("PARLAY_OPTIONAL_COVERS_PRICE_ONLY_OK")
