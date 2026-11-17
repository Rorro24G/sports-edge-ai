"""Smoke test: 3 borradores documentados de Covers en Streamlit, sin API."""
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from streamlit.testing.v1 import AppTest
from unittest.mock import patch as content_patch
# Keep unrelated content services independent of the network in UI tests.
content_patch("src.news_ui.cached_news", return_value={"articles": [], "checked_at_utc": "offline fixture"}).start()
content_patch("src.parlay_ui.cached_live_report", return_value={"leagues": {}, "generated_at_utc": "offline fixture"}).start()

today = datetime.now(ZoneInfo("America/Mexico_City")).date().isoformat()
report = {"date_cdmx": today, "generated_at_utc": datetime.now(
    ZoneInfo("UTC")).isoformat(), "leagues": {}}
for league in ("NBA", "NHL", "NFL"):
    names = (["Charlotte @ Los Angeles", "Detroit @ San Antonio",
              "Portland @ Minnesota", "Utah @ Boston"] if league == "NBA"
             else ["Edmonton @ Florida", "Dallas @ Vegas", "Toronto @ Chicago",
                   "Nashville @ Minnesota"] if league == "NHL"
             else [])
    report["leagues"][league] = {
        "coverage": {"covers": "consultado", "espn": "consultado"},
        "events": [{
            "liga": league, "partido": match,
            "fecha_cdmx": today, "hora_cdmx": "23:59",
            "fuente_covers": "https://www.covers.com/picks/" + league.lower(),
            "momios_covers": ["+117", "-125"],
            "proyeccion_covers": ([104.2, 112.5] if league == "NBA" else [2.8, 3.4]),
            "espn": {"evento": str(40000 + i), "fuente": "https://www.espn.com/"},
        } for i, match in enumerate(names)],
    }

with patch("src.brain_dashboard.load_today_snapshot", return_value=report), patch("src.parlay_ui.load_today_snapshot", return_value=report):
    app = AppTest.from_file("../app.py", default_timeout=45).run()
    assert not app.exception, [str(x.message) for x in app.exception]
    visible = "\n".join(str(x.value) for x in app.markdown)
    assert "Combinadas de referencia" in visible, "Faltan borradores parlays"
    assert "Alternativa 1" in " ".join(str(x.label) for x in app.expander)
    assert "ODDS_API_KEY" not in visible, "No mostrar secretos técnicos en pantalla"
    app = app.button(key="discutir_parlay_0").click().run()
    assert not app.exception, [str(x.message) for x in app.exception]
    draft = app.session_state["parlay_chat_question"]
    assert "Fuente:" in draft and "Covers" in draft
    assert "NO es una cuota real" in draft
    print("STREAMLIT_PARLAY_REVIEW_UI_OK")

