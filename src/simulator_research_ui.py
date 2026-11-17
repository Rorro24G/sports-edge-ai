"""Punto de entrada para simulaciones informadas por RESULTADOS ESPN reales.

Las medias se calculan con el historial anterior al partido, sin cuota
inventada ni resultado futuro. El estadio/tribuna es un dibujo ilustrativo,
no una reproducción de jugadas ni modelo de tracking.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

from .live_board import CalendarSourceError
from .team_form import TeamFormError, recent_team_form, scenario_from_forms
from .simulations import GameScenario, simulate_totals
from .simulation_view import render_results

LOCAL = ZoneInfo("America/Mexico_City")


def render(*, board_fetch, team_fetch) -> None:
    st.subheader("Escenario real · resultados históricos ESPN")
    st.caption(
        "Elige partido y fecha: recuperamos los resultados anteriores de ambos "
        "equipos y generamos 10.000 marcadores hipotéticos. "
        "No es una simulación jugada a jugada ni una probabilidad calibrada."
    )
    c1, c2 = st.columns([1, 2])
    with c1:
        league = st.selectbox("Liga del escenario", ["NFL", "NBA"],
                              key="real_sim_league")
    with c2:
        day = st.date_input("Fecha del encuentro (Ciudad de México)",
                            value=datetime.now(LOCAL).date(), key="real_sim_day")
    if st.button("Buscar partidos ESPN", key="real_sim_find"):
        try:
            response = board_fetch(league, day)
        except (CalendarSourceError, OSError, ValueError) as exc:
            st.warning("No se pudo obtener la jornada de ESPN: " + str(exc))
            st.session_state.pop("real_sim_board", None)
        else:
            valid_games = [
                game for game in response.get("games", [])
                if game.get("sport") == league
                and game.get("away_team_id") and game.get("home_team_id")
                and str(game.get("local_date")) == day.isoformat()
            ]
            st.session_state["real_sim_board"] = {
                "league": league, "date": day.isoformat(),
                "games": valid_games, "checked_at_utc": response.get("checked_at_utc"),
            }
            st.session_state.pop("real_sim_result", None)

    saved = st.session_state.get("real_sim_board")
    if not saved or saved["league"] != league or saved["date"] != day.isoformat():
        st.info("Busca primero los partidos de ESPN para obtener los equipos reales.")
        return
    games = saved["games"]
    if not games:
        st.warning("ESPN no devolvió un encuentro con IDs verificables para esta liga/fecha.")
        return
    options = [
        f"{g['away']} @ {g['home']} · {g['local_time']} CDMX" for g in games
    ]
    selected = st.selectbox("Encuentro", options, key="real_sim_match")
    game = games[options.index(selected)]
    st.caption("Fuente: ESPN · partido " + str(game.get("event_id", "")) +
               " · consulta " + str(saved.get("checked_at_utc", "")) + " UTC")
    if game.get("source_url"):
        st.link_button("Ver encuentro en ESPN", game["source_url"])
    line = st.number_input(
        "Línea de puntos total que quieres estudiar (introducida por ti)",
        min_value=0.5, max_value=400.0,
        value=45.5 if league == "NFL" else 222.5, step=0.5,
        key="real_sim_total_line",
    )
    st.caption("Esta línea es introducida manualmente; NO se presenta como "
               "un momio o una línea confirmada de una casa de apuestas.")
    if st.button("Simular 10.000 resultados con historial ESPN",
                 key="real_sim_run", use_container_width=True):
        away_id = str(game["away_team_id"])
        home_id = str(game["home_team_id"])
        try:
            away_data = team_fetch(league, away_id, day)
            home_data = team_fetch(league, home_id, day)
            away_form = recent_team_form(away_data["games"], last=10, minimum=5)
            home_form = recent_team_form(home_data["games"], last=10, minimum=5)
            params = scenario_from_forms(
                league, away_form, home_form, total_line=float(line)
            )
            allowed = {field for field in GameScenario.__dataclass_fields__}
            scenario = GameScenario(**{k: v for k, v in params.items() if k in allowed})
            result = simulate_totals(scenario)
        except (TeamFormError, OSError, ValueError, KeyError, TypeError) as exc:
            st.warning(
                "Sin un historial ESPN completo de ambos equipos no fabricamos "
                "estimaciones ni desviaciones: " + str(exc)
            )
            st.session_state.pop("real_sim_result", None)
        else:
            st.session_state["real_sim_result"] = {
                "game_key": (league, day.isoformat(), game["event_id"]),
                "scenario": scenario, "result": result,
                "away_form": away_form, "home_form": home_form,
                "away_source": away_data["source_url"],
                "home_source": home_data["source_url"],
                "away_name": game["away"], "home_name": game["home"],
                "method": params["method"],
            }
    analysis = st.session_state.get("real_sim_result")
    if not analysis:
        return
    if analysis["game_key"] != (league, day.isoformat(), game["event_id"]):
        return
    render_results(
        analysis["scenario"], analysis["result"],
        away_name=analysis["away_name"], home_name=analysis["home_name"],
        source_note="Estadísticas de los últimos partidos de temporada regular ESPN",
    )
    st.markdown("#### Cómo calculamos este escenario")
    st.write(analysis["method"])
    a, b = st.columns(2)
    for col, side, label in (
        (a, analysis["away_form"], analysis["away_name"]),
        (b, analysis["home_form"], analysis["home_name"]),
    ):
        with col:
            st.markdown("**" + label + "**")
            st.metric("Partidos históricos", side["partidos"])
            st.metric("Puntos a favor por partido",
                      f"{side['puntos_anotados_media']:.2f}")
            st.metric("Puntos concedidos por partido",
                      f"{side['puntos_recibidos_media']:.2f}")
            st.caption("Racha reciente (W/L): " + side["racha"])
            st.dataframe(
                [{"Fecha CDMX": r["date"], "Rival": r["opponent"],
                  "Anotados": r["points_for"], "Recibidos": r["points_against"],
                  "Resultado": r["result"]}
                 for r in side["partidos_reales"]],
                hide_index=True, use_container_width=True,
            )
    st.link_button("Origen del historial visitante (ESPN)", analysis["away_source"])
    st.link_button("Origen del historial local (ESPN)", analysis["home_source"])
    st.warning(
        "Los 10.000 sorteos son un modelo experimental de puntuación, NO un "
        "sistema entrenado y calibrado para apostar. Las lesiones, el descanso, "
        "los esquemas y la correlación real no están modelados. No calcula EV "
        "ni porcentaje de bank recomendado."
    )
