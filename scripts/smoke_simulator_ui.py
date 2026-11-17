"""AppTest real Simulaciones: schedule + histórico ESPN fake, 10k draws, SVG."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest

today = datetime.now(ZoneInfo("America/Mexico_City")).date()


def board(league, day):
    return {
        "games": [{
            "sport": league, "away": "Baltimore Ravens",
            "home": "Los Angeles Chargers",
            "local_date": day,
            "local_time": "20:00", "event_id": "40123489",
            "away_team_id": "33", "home_team_id": "24",
            "status": "SCHEDULED",
            "source_url": "https://www.espn.com/nfl/game",
        }] if league == "NFL" else [],
        "checked_at_utc": "2026-11-17T12:00:00Z",
        "url": "https://www.espn.com/nfl/scoreboard",
    }


def team_form(league, team_id, day):
    return {
        "sport": league, "team_id": team_id,
        "source_url": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/" +
                      team_id + "/schedule",
        "checked_at_utc": "2026-11-17T12:00:00Z",
        "games": [
            {
                "date": (day - timedelta(days=7 * (i + 1))).isoformat(),
                "points_for": 20 + ((i * 3 + int(team_id)) % 15),
                "points_against": 17 + ((i * 2 + int(team_id)) % 12),
                "result": "W", "home": bool(i % 2),
                "event_id": str(i + 401000), "opponent": "Other",
            } for i in range(10)
        ],
    }


with (
    patch("src.live_board.fetch_scoreboard", side_effect=board),
    patch("src.team_form.fetch_team_schedule", side_effect=team_form),
):
    app = AppTest.from_file("../app.py", default_timeout=40).run()
    assert not app.exception, [str(e.message) for e in app.exception]
    app = app.button(key="real_sim_find").click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    assert "real_sim_match" in [x.key for x in app.selectbox]
    app = app.button(key="real_sim_run").click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    simulation = app.session_state["real_sim_result"]
    assert simulation["result"].simulations == 10_000
    assert simulation["away_form"]["partidos"] == 10
    assert simulation["result"].histogram
    visible = "\n".join(str(x.value) for x in app.markdown)
    assert "sim-stadium" in visible, "No aparece el campo NFL"
    assert "VISUALIZACIÓN ILUSTRATIVA" in visible
    assert "NO ES PICK VALIDADO" in "\n".join(str(x.message) for x in app.warning)
    print("STREAMLIT_ESPN_SIMULATOR_UI_OK")
