"""End-to-end: ESPN outages differ from no fixtures and no eligible picks.

The analysis is shared by Picks and Parlays, and must never call Covers
unless the user explicitly requests external market prices.
"""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest
from src.live_board import CalendarSourceError

MX = ZoneInfo("America/Mexico_City")
today = datetime.now(MX).date()


def scoreboard(league, day):
    if league == "NBA":
        raise CalendarSourceError("ESPN service unavailable")
    if league == "NFL":
        return {"games": [], "checked_at_utc": "2026-11-18T13:00:00Z"}
    return {"games": [], "checked_at_utc": "2026-11-18T13:00:00Z"}


with (
    patch("src.live_board.fetch_scoreboard", side_effect=scoreboard),
    patch("src.covers_public.fetch_public_picks",
          side_effect=AssertionError("No Covers needed for diagnosis")),
):
    app = AppTest.from_file("../app.py", default_timeout=45)
    app.session_state["brain_section"] = "picks"
    app = app.run()
    assert not app.exception, [str(e.message) for e in app.exception]
    warnings = "\n".join(str(x.message) for x in app.warning)
    errors = "\n".join(str(x.message) for x in app.error)
    info = "\n".join(str(x.message) for x in app.info)
    assert "ESPN no respondió para: NBA" in warnings, warnings
    assert "fallaron las fuentes ESPN" not in errors, errors
    assert "No hay encuentros futuros" in info, info
    labels = {m.label: str(m.value) for m in app.metric}
    assert labels["NBA · calendario ESPN"] == "Sin conexión", labels
    assert labels["NFL · calendario ESPN"] == "0", labels

    # Same source view in Parlays, not a separate Covers-dependent path.
    app = app.button(key="section_nav_parlays").click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    warnings = "\n".join(str(x.message) for x in app.warning)
    assert "Sin respuesta del calendario ESPN: NBA" in warnings, warnings
    assert "Parlays propios del cerebro" in "\n".join(str(x.value) for x in app.markdown)
    print("PICKS_AND_PARLAYS_ESPN_SOURCE_DIAGNOSTICS_OK")
