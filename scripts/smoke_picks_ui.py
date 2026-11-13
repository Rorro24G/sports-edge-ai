"""Prueba real de renderizado de Streamlit, sin credenciales ni peticiones externas."""
from datetime import datetime
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

SAMPLE = {
    "league": "NBA", "page_date": "2026-11-13",
    "checked_at_utc": "2026-11-13T16:00:00+00:00",
    "events": [{
        "liga": "NBA", "partido": "Toronto @ Philadelphia",
        "fecha_cdmx": "2026-11-13", "hora_cdmx": "18:00",
        "proyeccion_visitante": 107.0, "proyeccion_local": 115.0,
        "momio_visitante": "+210", "momio_local": "-250",
        "totales_publicados": "o223.5 -110",
        "spreads_publicados": "+6.5 -110",
        "probabilidades_publicadas": None,
        "tipo_mercados": "cuotas_americanas",
        "fuente": "https://www.covers.com/picks/nba",
    }],
}

def fake_covers(league, target):
    return dict(SAMPLE, league=league, events=SAMPLE["events"] if league == "NBA" else [])

def fake_board(league, target):
    return {
        "games": ([{
            "sport": "NBA", "away": "Toronto Raptors", "home": "Philadelphia 76ers",
            "local_time": "18:00", "status": "SCHEDULED",
            "event_id": "401123456", "source_url": "https://www.espn.com/nba/game",
        }] if league == "NBA" else []),
        "checked_at_utc": "2026-11-13T16:00:00+00:00",
    }

def fake_summary(league, event_id):
    return {
        "venue": "Example Arena", "injuries": [], "leaders": [],
        "news": [{"Titular ESPN": "Noticia del partido",
                  "Enlace": "https://www.espn.com/nba/story/_/id/123/preview"}],
        "checked_at_utc": "2026-11-13T16:00:00+00:00",
    }

with (
    patch("src.covers_public.fetch_public_picks", side_effect=fake_covers),
    patch("src.live_board.fetch_scoreboard", side_effect=fake_board),
    patch("src.pick_context.fetch_summary", side_effect=fake_summary),
):
    app = AppTest.from_file("../app.py", default_timeout=40).run()
    assert not app.exception, [str(e.message) for e in app.exception]
    inputs = list(app.text_input)
    assert inputs, "No aparece el campo para preguntar por un partido"
    inputs[0].set_value("Analiza Toronto contra Philadelphia 13 de noviembre de 2026")
    buttons = [b for b in app.button if b.label == "Analizar partido"]
    assert len(buttons) == 1, "No se encontro el boton de Picks"
    app = buttons[0].click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    visible = "\n".join(str(x.value) for x in app.markdown)
    assert "Toronto @ Philadelphia" in visible, "No se renderizo el partido"
    assert "Momios por casa de apuestas" in visible, "Falta panel de momios"
    assert "Noticias" in visible or "noticias" in visible, "Falta panel de contexto"
    print("STREAMLIT_PICKS_UI_OK")
