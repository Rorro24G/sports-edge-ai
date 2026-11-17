"""Sports Edge AI: interfaz privada de laboratorio para consultas deportivas.

Ejecucion: pip install -r requirements-web.txt && streamlit run app.py
Aviso: este MVP NO publica picks, no opera apuestas ni contiene modelos validados.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from src.simulations import GameScenario, simulate_totals
from src.live_board import fetch_scoreboard, CalendarSourceError
from src.live_odds import odds_for_day
from src.covers_reference import picks_links, consensus_link, PUBLIC_MONEY_EXPLANATION
from src.covers_public import fetch_public_picks, CoversSourceError
from src.pick_context import match_espn_event, fetch_summary, ContextSourceError
from src.odds_api import OddsAPIError
from src.web_data import find_games, load_fixture
from src.web_query import interpret_request
from src.team_form import fetch_team_schedule
from src.simulator_research_ui import render as render_real_simulator
from src.simulation_view import render_results as show_simulated_scenario
from src.player_props import fetch_roster, fetch_gamelog, parse_player_question
from src.player_props_ui import render_player_research
from src.prop_offers import fetch_player_prop_offers
from src.brain_dashboard import render_brain_header, render_morning_snapshot

st.set_page_config(
    page_title="Sports Edge AI | Cerebro",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.brain_portal import apply_theme, render_navigation
apply_theme()
section = render_navigation()

@st.cache_data(ttl=600, show_spinner=False)
def cached_scoreboard(sport, target):
    return fetch_scoreboard(sport, target)

@st.cache_data(ttl=600, show_spinner=False)
def cached_covers(league, target):
    return fetch_public_picks(league, target)

@st.cache_data(ttl=600, show_spinner=False)
def cached_pick_summary(league, event_id):
    return fetch_summary(league, event_id)

@st.cache_data(ttl=300, show_spinner=False)
def cached_odds(key, sports, target):
    return odds_for_day(key, sports, target)

@st.cache_data(ttl=21600, show_spinner=False)
def cached_player_roster(team_id):
    return fetch_roster(team_id)

@st.cache_data(ttl=600, show_spinner=False)
def cached_player_gamelog(player_id, target):
    return fetch_gamelog(player_id, target)

@st.cache_data(ttl=180, show_spinner=False)
def cached_prop_offers(api_key, game, target, player_name, stat, direction, line):
    return fetch_player_prop_offers(
        api_key, game=game, target=target, player_name=player_name,
        stat=stat, direction=direction, line=line,
    )

@st.cache_data(ttl=3600, show_spinner=False)
def cached_team_schedule(sport, team_id, target):
    return fetch_team_schedule(sport, team_id, target)

def safe_odds_key():
    try:
        return st.secrets.get("ODDS_API_KEY", "")
    except (FileNotFoundError, OSError):
        return ""

if section == "picks":
    render_morning_snapshot()
    st.markdown("## Explorar picks")
    st.caption("Encuentros de ESPN, proyecciones y momios publicados por Covers.")
    with st.form("sports_query"):
        prompt = st.text_input(
            "¿Qué partido, jugador o mercado quieres analizar?",
            value="",
            placeholder="NBA hoy · Knicks vs Raptors · Over de 24.5 puntos",
        )
        submitted = st.form_submit_button("Analizar partido", use_container_width=True)
    if submitted:
        try:
            st.session_state["last_analysis_request"] = interpret_request(prompt)
            st.session_state["last_analysis_text"] = prompt
            st.session_state.pop("selected_match", None)
        except (ValueError, TypeError) as exc:
            st.session_state.pop("last_analysis_request", None)
            st.error("Fecha solicitada no válida: " + str(exc))
    if st.button("Actualizar datos de Picks ahora", key="refresh_picks"):
        cached_covers.clear()
        cached_scoreboard.clear()
        cached_pick_summary.clear()
        cached_odds.clear()
        cached_player_roster.clear()
        cached_player_gamelog.clear()
        cached_prop_offers.clear()
        st.toast("Datos actualizados")
    request = st.session_state.get("last_analysis_request")
    if request is None:
        # A live board appears without making the user submit the default query.
        request = interpret_request("NBA NFL NHL hoy")
        st.session_state["last_analysis_request"] = request
        st.session_state["last_analysis_text"] = "NBA NFL NHL hoy"
    if request is not None:
        st.caption("Fecha: " + request.target_date.strftime("%d/%m/%Y")
                   + " · Ligas: " + ", ".join(request.sports) + " · CDMX")
        latest_question = st.session_state.get("last_analysis_text", "")
        player_question = parse_player_question(latest_question)
        if player_question:
            if "NBA" not in request.sports:
                st.warning("Las consultas de puntos/rebotes/asistencias por jugador "
                           "están conectadas primero para NBA. Esa liga no está "
                           "incluida en tu consulta.")
            else:
                try:
                    player_board = cached_scoreboard("NBA", request.target_date)
                except CalendarSourceError:
                    st.warning("ESPN no entregó los equipos NBA de esta fecha. "
                               "No es posible verificar el jugador con seguridad.")
                else:
                    render_player_research(
                        latest_question, request.target_date,
                        games=player_board["games"],
                        roster_fetch=cached_player_roster,
                        gamelog_fetch=cached_player_gamelog,
                        prop_odds_fetch=cached_prop_offers if safe_odds_key() else None,
                        prop_api_key=safe_odds_key(),
                    )
        links = picks_links(request.sports) if not player_question else []
        published = []
        covers_errors = []
        for league, _link in links:
            try:
                covers = cached_covers(league, request.target_date)
            except (CoversSourceError, ValueError):
                covers_errors.append(league)
                continue
            published.extend(covers["events"])

        # ESPN supplies the complete calendar; Covers enriches a verified
        # match with actual published moneyline and score projections.
        boards = {}
        if not player_question:
            for league in request.sports:
                if league not in ("NBA", "NFL", "NHL"):
                    continue
                try:
                    boards[league] = cached_scoreboard(
                        league, request.target_date
                    )["games"]
                except (CalendarSourceError, KeyError, ValueError):
                    boards[league] = []
            from src.picks_feed import live_picks_catalog, pick_catalog_rows
            published = live_picks_catalog(published, boards, request.target_date)
        from src.match_report import relevant_matches
        ranked, specific_request = relevant_matches(
            published, st.session_state.get("last_analysis_text", "")
        )
        if not player_question and ranked:
            st.markdown("### Partidos y momios")
            st.dataframe(
                pick_catalog_rows(ranked), use_container_width=True,
                hide_index=True,
            )
            st.caption("ML = moneyline americano publicado por Covers. «—» indica "
                       "que esa cuota no está verificada; no se sustituyen porcentajes.")
        if covers_errors and not player_question:
            st.caption("Covers temporalmente no disponible: " + ", ".join(covers_errors))
        if player_question:
            pass  # La consulta de jugador ya se respondió con evidencia ESPN.
        elif ranked:
            options = [
                f"{game['liga']} · {game['partido']} · {game['hora_cdmx']} CDMX"
                + (f" · ML {game['momio_visitante']} / {game['momio_local']}"
                   if game.get('momio_visitante') and game.get('momio_local') else "")
                for game in ranked
            ]
            chosen = st.selectbox("Seleccionar partido", options, key="selected_match")
            game = ranked[options.index(chosen)]
            st.markdown("### " + game["partido"] + " · " + game["liga"])
            st.caption("Fecha " + game["fecha_cdmx"] + " · "
                       + game["hora_cdmx"] + " CDMX")
            left, right = st.columns(2)
            left.metric("Proyección visitante",
                        str(game["proyeccion_visitante"])
                        if game["proyeccion_visitante"] is not None else "No disponible")
            right.metric("Proyección local",
                         str(game["proyeccion_local"])
                         if game["proyeccion_local"] is not None else "No disponible")
            from src.pick_evidence_ui import render_covers_evidence
            if game.get("origen") == "Covers":
                render_covers_evidence(game)
                if game.get("fuente"):
                    st.link_button("Consultar Covers", game["fuente"])
            else:
                st.caption("Partido ESPN: Covers no tiene una proyección y "
                           "moneyline verificables para este juego.")
            from src.market_summary import game_market_probabilities
            market_p = game_market_probabilities(game)
            st.markdown("**Umbral implícito de los momios**")
            if all(value is None for value in market_p.values()):
                st.caption("Covers no publicó moneylines verificables para este partido.")
            else:
                p1, p2 = st.columns(2)
                if market_p["visitante"] is not None:
                    p1.metric("Visitante · umbral de equilibrio", f"{market_p['visitante']:.2f}%")
                if market_p["local"] is not None:
                    p2.metric("Local · umbral de equilibrio", f"{market_p['local']:.2f}%")
                st.caption("Calculado del precio publicado, con margen comercial. "
                           "No es una probabilidad predictiva.")
            api_key = safe_odds_key()
            if api_key:
                with st.expander("Momios adicionales verificados de otras casas", expanded=False):
                    from src.match_report import verified_market_rows
                    try:
                        external_rows = cached_odds(api_key, (game["liga"],), request.target_date)
                    except (OddsAPIError, ValueError) as exc:
                        st.warning("No se pudieron actualizar los momios externos: " + str(exc))
                    else:
                        confirmed = verified_market_rows(game, external_rows)
                        if confirmed:
                            st.dataframe(confirmed, use_container_width=True, hide_index=True)
                            st.caption("Fuente: proveedor de momios, actualizado "
                                       "periódicamente. No es una probabilidad propia.")
                        else:
                            st.caption("No hubo cuotas externas coincidentes con liga, "
                                       "equipos, fecha y hora de este encuentro.")
            with st.expander("Consenso y contexto del mercado"):
                st.caption("El consenso de Covers refleja participaciones de concursos, "
                           "no el dinero apostado en casas.")
            st.markdown("**Jugadores, bajas, lesiones y contexto de ESPN**")
            try:
                espn_board = cached_scoreboard(game["liga"], request.target_date)
            except CalendarSourceError:
                st.warning("No fue posible contrastar el partido con el calendario de ESPN.")
            else:
                verified_game = match_espn_event(game, espn_board["games"])
                if verified_game is None:
                    st.info(
                        "No se encontró una coincidencia inequívoca entre ambos equipos "
                        "en ESPN para esta fecha. No atribuiremos lesiones o noticias "
                        "de otro partido a esta ficha."
                    )
                else:
                    st.caption(
                        "ESPN · estado " + verified_game["status"]
                        + " · actualizado " + espn_board["checked_at_utc"] + " (UTC)"
                    )
                    st.link_button("Ver partido confirmado por ESPN",
                                   verified_game["source_url"])
                    try:
                        espn = cached_pick_summary(game["liga"], verified_game["event_id"])
                    except (ContextSourceError, ValueError):
                        st.warning(
                            "ESPN no entregó un resumen válido para este encuentro. "
                            "No se mostrarán reportes antiguos ni suposiciones."
                        )
                    else:
                        st.caption("Resumen ESPN consultado " + espn["checked_at_utc"] + " (UTC)")
                        if espn["venue"]:
                            st.write("Sede: " + espn["venue"])
                        if espn["injuries"]:
                            st.markdown("**Reporte de lesiones y disponibilidad publicado por ESPN**")
                            st.dataframe(espn["injuries"], use_container_width=True,
                                         hide_index=True)
                            st.caption(
                                "Los estados corresponden al momento de consulta, "
                                "no garantizan la alineación final ni sustituyen al reporte oficial."
                            )
                        else:
                            st.info(
                                "Sin reporte de lesiones disponible en este resumen de ESPN. "
                                "No significa que los jugadores estén todos sanos o disponibles."
                            )
                        if espn["leaders"]:
                            st.markdown("**Líderes estadísticos publicados por ESPN**")
                            st.dataframe(espn["leaders"], use_container_width=True,
                                         hide_index=True)
                        else:
                            st.caption(
                                "ESPN no proporcionó líderes estadísticos "
                                "utilizables para este partido."
                            )
                        if espn["news"]:
                            st.markdown("**Noticias sobre el encuentro publicadas por ESPN**")
                            for article in espn["news"]:
                                st.markdown("- [" + article["Titular ESPN"].replace("[", "").replace("]", "") + "](" + article["Enlace"] + ")")
                            st.caption("Titulares enlazados a ESPN; su contenido no se considera una lesión ni una alineación confirmada.")
                        else:
                            st.caption("ESPN no aportó artículos específicos en el resumen de este encuentro.")
            st.caption("Selecciones y precios de Covers son referencias externas; "
                       "Sports Edge AI todavía no tiene un modelo propio calibrado.")
        else:
            if published and specific_request:
                st.warning(
                    "Los equipos solicitados no coinciden con los partidos publicados "
                    "para esta fecha. Revisa el nombre o cambia la fecha."
                )
                st.dataframe(
                    [{"Liga": row["liga"], "Partido publicado": row["partido"],
                      "Hora CDMX": row["hora_cdmx"]} for row in published],
                    use_container_width=True, hide_index=True
                )
            else:
                st.caption("No hay partidos verificables para esa fecha y ligas.")
        if not player_question and ("ATP" in request.sports or "WTA" in request.sports):
            st.info("Los conectores de tenis ATP/WTA siguen pendientes de validación.")


if section == "asistente":
    from src.assistant_ui import render as render_assistant
    render_assistant(
        board_fetch=cached_scoreboard,
        covers_fetch=cached_covers,
        roster_fetch=cached_player_roster,
        gamelog_fetch=cached_player_gamelog,
        prop_odds_fetch=cached_prop_offers if safe_odds_key() else None,
        prop_api_key=safe_odds_key(),
    )

if section == "simulaciones":
    render_real_simulator(
        board_fetch=cached_scoreboard,
        team_fetch=cached_team_schedule,
    )
    st.divider()
    with st.expander("Laboratorio manual · parámetros hipotéticos", expanded=False):
        st.caption(
            "Para experimentar puedes introducir medias y desviaciones manuales. "
            "Estas cifras NO son datos ESPN ni proyecciones verificadas."
        )
        with st.form("simulator"):
            c1, c2 = st.columns(2)
            with c1:
                sport = st.selectbox("Deporte", ["NFL", "NBA"])
                away_mean = st.number_input(
                    "Puntos esperados visitante (hipotético)",
                    min_value=0.0, max_value=200.0,
                    value=22.0 if sport == "NFL" else 110.0, step=0.5
                )
                away_sd = st.number_input(
                    "Desviación visitante", min_value=0.1,
                    max_value=60.0, value=9.0 if sport == "NFL" else 12.0, step=0.5
                )
            with c2:
                home_mean = st.number_input(
                    "Puntos esperados local (hipotético)",
                    min_value=0.0, max_value=200.0,
                    value=24.0 if sport == "NFL" else 114.0, step=0.5
                )
                home_sd = st.number_input(
                    "Desviación local", min_value=0.1,
                    max_value=60.0, value=9.0 if sport == "NFL" else 12.0, step=0.5
                )
                line = st.number_input(
                    "Línea de puntos total (hipotética)",
                    min_value=0.0, max_value=400.0,
                    value=45.5 if sport == "NFL" else 223.5, step=0.5
                )
            correlation = st.slider(
                "Correlación de marcadores (hipótesis)",
                min_value=-0.9, max_value=0.9, value=0.0, step=0.05
            )
            run_sim = st.form_submit_button(
                "Simular 10.000 escenarios manuales", use_container_width=True
            )
        if run_sim:
            try:
                scenario = GameScenario(
                    sport=sport, away_mean=away_mean, home_mean=home_mean,
                    away_sd=away_sd, home_sd=home_sd,
                    score_correlation=correlation, total_line=line,
                )
                result = simulate_totals(scenario)
            except ValueError as exc:
                st.error(str(exc))
            else:
                show_simulated_scenario(
                    scenario, result,
                    source_note="Medias y desviaciones introducidas manualmente; "
                                "NO son datos reales de equipos",
                )

if section == "calendario":
    st.subheader("Calendario actualizado por fecha")
    st.caption(
        "Consulta los partidos de NBA, NFL y NHL en ESPN bajo demanda. "
        "La consulta se renueva automáticamente como máximo cada diez minutos; "
        "no depende de una fecha fija guardada."
    )
    day = st.date_input("Fecha en Ciudad de México",
                        value=datetime.now(ZoneInfo("America/Mexico_City")).date(),
                        key="calendar_date")
    leagues = st.multiselect("Ligas", ["NBA", "NFL", "NHL"],
                             default=["NBA", "NFL", "NHL"], key="calendar_leagues")
    if st.button("Actualizar calendario ahora"):
        cached_scoreboard.clear()
    calendar_rows = []
    for league in leagues:
        try:
            board = cached_scoreboard(league, day)
        except CalendarSourceError:
            st.warning(league + ": no se pudo actualizar el calendario; no se usarán datos antiguos.")
            continue
        st.caption(league + " · consulta " + board["checked_at_utc"] + " (UTC)")
        if not board["games"]:
            st.info("No se encontraron juegos de " + league + " para esa fecha en ESPN.")
        for game in board["games"]:
            calendar_rows.append({
                "Liga": game["sport"],
                "Visitante": game["away"],
                "Local": game["home"],
                "Hora CDMX": game["local_time"],
                "Estado": game["status"],
                "Fuente": game["source_url"],
            })
    if calendar_rows:
        st.dataframe(sorted(calendar_rows, key=lambda row: (row["Hora CDMX"], row["Liga"])),
                     use_container_width=True, hide_index=True)
    st.caption("ATP/WTA: calendario por conectar. La ausencia de datos no equivale a partido cancelado.")

if section == "noticias":
    from src.news_ui import render as render_news
    render_news()


if section == "estado":
    st.subheader("Conexiones y seguridad")
    st.markdown(
        "- **GitHub:** código y pruebas versionados.\n"
        "- **Calendario:** consulta bajo demanda a ESPN de NBA, NFL y NHL; la fuente puede fallar.\n"
        "- **ATP/WTA:** proveedor de calendario por conectar.\n"
        "- **Momios:** precios publicados por Covers; otras casas solo se muestran cuando están disponibles.\n"
        "- **Covers:** lector HTML de proyecciones/mercados públicos NBA/NFL/NHL, con enlaces a la fuente; puede fallar por cambios o bloqueos.\n"
        "- **TEAM MÉXICO:** sin acceso autorizado a cuotas en tiempo real.\n"
        "- **Modelos predictivos:** entrenamiento y calibración pendientes.\n"
        "- **OneDrive personal:** sincronización todavía sin autenticar.\n"
        "- **Simulador:** laboratorio matemático reproducible; no genera picks."
    )
    st.warning(
        "Esta interfaz no tiene inicio de sesión integrado. "
        "Debe protegerse con autenticación del proveedor de alojamiento ANTES de publicarla "
        "o almacenar datos privados. No contiene contraseñas ni tokens."
    )
    st.caption("Sin operaciones reales. Historial de predicciones y tamaño de apuesta disponibles tras validación.")

if section == "parlays":
    from src.parlay_ui import render as render_parlay
    render_parlay()


if section == "historial":
    from src.ledger_ui import render
    render()

