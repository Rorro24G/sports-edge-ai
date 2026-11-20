"""UI smoke: rich sections and direct cross-section navigation, offline."""
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest


def board(league, day):
    found = [{
        "sport": league, "away": "Boston Celtics",
        "home": "New York Knicks", "away_team_id": "2",
        "home_team_id": "18", "local_date": day,
        "local_time": "19:30", "status": "PRE",
        "event_id": "401123", "away_score": None, "home_score": None,
        "source_url": "https://www.espn.com/nba/game/_/gameId/401123",
    }] if league == "NBA" else []
    return {"games": found, "checked_at_utc": "2026-11-18T11:20:00Z",
            "url": "https://www.espn.com/nba/scoreboard"}

feed = {
    "checked_at_utc": "2026-11-18T11:20:00Z",
    "articles": [{
        "headline": "Celtics roster update ahead of tipoff",
        "published_utc": "2026-11-18T11:00:00+00:00",
        "url": "https://www.espn.com/nba/story/_/id/123/news",
    }],
}

with (
    patch("src.news_ui.cached_news", return_value=feed),
    patch("src.live_board.fetch_scoreboard", side_effect=board),
    patch("src.parlay_ui.cached_live_report",
          return_value={"leagues": {}, "generated_at_utc": "offline fixture"}),
):
    app = AppTest.from_file("../app.py", default_timeout=45)
    app.session_state["brain_section"] = "noticias"
    app = app.run()
    assert not app.exception, [x.message for x in app.exception]
    text = "\n".join(str(x.value) for x in app.markdown)
    assert "Sala de noticias" in text
    assert "Celtics roster update" in text
    assert len([b for b in app.button if str(b.key).startswith("section_nav_")]) == 6
    app = app.button(key="section_nav_calendario").click().run()
    assert not app.exception, [x.message for x in app.exception]
    assert app.session_state["brain_section"] == "calendario"
    assert app.session_state["brain_transition_seq"] == 1
    text = "\n".join(str(x.value) for x in app.markdown)
    assert "Agenda deportiva" in text
    assert "Boston Celtics" in text and "New York Knicks" in text
    assert any(m.label == "Encuentros encontrados" and str(m.value) == "1"
               for m in app.metric)
    app = app.button(key="section_nav_simulaciones").click().run()
    assert not app.exception, [x.message for x in app.exception]
    assert app.session_state["brain_section"] == "simulaciones"
    assert app.session_state["brain_transition_seq"] == 2
    assert "Configura un escenario real" in "\n".join(str(x.value) for x in app.markdown)
    app = app.button(key="section_nav_historial").click().run()
    assert not app.exception, [x.message for x in app.exception]
    assert app.session_state["brain_transition_seq"] == 3
    assert "Panel de actividad privada" in "\n".join(str(x.value) for x in app.markdown)
    app = app.button(key="back_to_brain").click().run()
    assert not app.exception, [x.message for x in app.exception]
    assert app.session_state["brain_section"] is None
    assert app.session_state["brain_visit"] >= 1
    print("VISUAL_SECTIONS_AND_CROSS_NAV_OK")
