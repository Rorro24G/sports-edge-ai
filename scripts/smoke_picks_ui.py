"""Prueba real de renderizado de Streamlit, sin credenciales ni peticiones externas."""
from datetime import datetime
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from unittest.mock import patch as content_patch
# Keep unrelated content services independent of the network in UI tests.
content_patch("src.news_ui.cached_news", return_value={"articles": [], "checked_at_utc": "offline fixture"}).start()
content_patch("src.parlay_ui.cached_live_report", return_value={"leagues": {}, "generated_at_utc": "offline fixture"}).start()

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
            "away_team_id": "28", "home_team_id": "20",
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

def fake_roster(team_id):
    return {"athletes": (
        [{"id": "4433134", "name": "Scottie Barnes", "team_id": "28",
          "injuries": [], "status": "Active"}] if team_id == "28" else []
    )}


def fake_gamelog(player_id, target):
    assert player_id == "4433134"
    return {
        "payload": {
            "labels": ["MIN", "REB", "AST", "PTS"],
            "events": {
                "4011": {"gameDate": "2026-11-12T02:00:00Z",
                         "opponent": {"abbreviation": "BOS"}},
                "4012": {"gameDate": "2026-11-11T02:00:00Z",
                         "opponent": {"abbreviation": "NYK"}},
            },
            "seasonTypes": [{
                "id": "2", "displayName": "2026-27 Regular Season",
                "categories": [{"events": [
                    {"eventId": "4011", "stats": ["35", "8", "7", "29"]},
                    {"eventId": "4012", "stats": ["34", "6", "6", "23"]},
                ]}],
            }],
        },
        "source_url": "https://www.espn.com/nba/player/gamelog/_/id/4433134",
        "checked_at_utc": "2026-11-13T12:00:00+00:00",
    }


with (
    patch("src.player_props.fetch_roster", side_effect=fake_roster),
    patch("src.player_props.fetch_gamelog", side_effect=fake_gamelog),
    patch("src.covers_public.fetch_public_picks", side_effect=fake_covers),
    patch("src.live_board.fetch_scoreboard", side_effect=fake_board),
    patch("src.pick_context.fetch_summary", side_effect=fake_summary),
):
    app = AppTest.from_file("../app.py", default_timeout=40).run()
    assert not app.exception, [str(e.message) for e in app.exception]
    initial_text = "\n".join(str(x.value) for x in app.markdown)
    assert "EL CEREBRO" in initial_text, "No apareció la portada neuronal nueva"
    assert "Radar del día" in initial_text, "No apareció el radar diario"
    inputs = list(app.text_input)
    assert inputs, "No aparece el campo para preguntar por un partido"
    inputs[0].set_value("Analiza Toronto contra Philadelphia 13 de noviembre de 2026")
    buttons = [b for b in app.button if b.label == "Analizar partido"]
    assert len(buttons) == 1, "No se encontro el boton de Picks"
    app = buttons[0].click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    visible = "\n".join(str(x.value) for x in app.markdown)
    assert "Toronto @ Philadelphia" in visible, "No se renderizo el partido"
    assert "Pick de referencia" in visible, "Falta sección de picks de Covers"
    assert "Lakers" not in visible, "No debe colarse un equipo ajeno a la ficha"
    assert "Mercados disponibles" in visible, "Falta panel de mercados de Covers"
    assert "Noticias" in visible or "noticias" in visible, "Falta panel de contexto"
    app.text_input[0].set_value("Analiza Dallas contra Phoenix 13 de noviembre de 2026")
    app = [b for b in app.button if b.label == "Analizar partido"][0].click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    visible = "\n".join(str(x.value) for x in app.markdown)
    assert any("Los equipos solicitados no coinciden" in str(x.value) for x in app.warning), "No avisa que el partido no existe"
    assert "### Toronto @ Philadelphia" not in visible, "Mostro un partido ajeno"
    app.text_input[0].set_value(
        "Over de 24.5 puntos de Scottie Barnes NBA 13 de noviembre de 2026"
    )
    app = [b for b in app.button if b.label == "Analizar partido"][0].click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    visible = "\n".join(str(x.value) for x in app.markdown)
    assert "Análisis de jugador" in visible, "No apareció análisis NBA por jugador"
    assert "Scottie Barnes" in visible, "No resolvió la identidad del jugador"
    assert "Over 24.5 puntos" in visible, "No encontró línea explícita del prop"
    assert "No se encontraron proyecciones extraíbles" not in visible, (
        "La respuesta de jugador no debe mostrar un error general de Covers"
    )
    assert "ODDS_API_KEY" not in visible, "No mostrar al usuario claves API ausentes"
    print("STREAMLIT_PLAYER_PROP_UI_OK")
    print("STREAMLIT_PICKS_UI_OK")

