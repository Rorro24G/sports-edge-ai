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

st.markdown(
    """
    <style>
    .stApp {background: radial-gradient(ellipse at 5% 0%, #103c31 0%, #0a1717 28%, #071112 72%); color: #edf8f3}
    .block-container {max-width: 1260px; padding-top: 2.2rem; padding-bottom: 3rem}
    h1, h2, h3 {color:#f1fff7 !important; letter-spacing:-.02em}
    p, label, .stMarkdown {color:#d5e8de}
    .hero {border:1px solid #285342; background:linear-gradient(125deg,#123e2e,#0b2422); padding:1.65rem 2rem; border-radius:18px; margin-bottom:1.3rem}
    .eyebrow {font-weight:800; font-size:.8rem; letter-spacing:.16em; color:#7ce6a7}
    .hero-title {font-size:2.5rem; font-weight:800; line-height:1.15; color:#f4fff8; margin:.4rem 0}
    .hero-sub {color:#bcddcc; font-size:1rem; margin-bottom:0}
    .status {padding:.45rem .75rem; border-radius:9px; display:inline-block; font-size:.83rem; font-weight:700; margin-right:.35rem; margin-bottom:.4rem}
    .green {background:#113b2c;color:#72efaa;border:1px solid #265f40}
    .red {background:#44242d;color:#ff9aa5;border:1px solid #763744}
    .amber {background:#473b1c;color:#ffd887;border:1px solid #746133}
    [data-testid="stMetric"] {background:#122c29; border:1px solid #245045; padding:1rem; border-radius:14px}
    [data-testid="stForm"] {border:1px solid #315a49; background:#0d2521; border-radius:16px}
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button {background:#38ca85 !important;color:#05221a!important;border-radius:12px!important; font-weight:800!important;border:0!important}
    a {color:#89e4af!important}

    .brain-command {background:radial-gradient(ellipse at 87% 44%,#174b43 0%,#0a2020 48%,#071416 85%);
        position:relative;display:flex;min-height:340px;padding:clamp(24px,5vw,56px);
        align-items:center;overflow:hidden;border:1px solid #2d7063;border-radius:24px;
        box-shadow:0 18px 70px #00000038;margin:0 0 1.25rem}
    .brain-command:before {content:"";position:absolute;inset:0;
        background:linear-gradient(90deg,#51ffbc0b 1px,transparent 1px),
        linear-gradient(0deg,#51ffbc0b 1px,transparent 1px);
        background-size:33px 33px;mask-image:linear-gradient(90deg,transparent 12%,#000 100%);pointer-events:none}
    .brain-copy {position:relative;z-index:2;width:60%;max-width:690px}
    .brain-eyebrow {display:flex;align-items:center;gap:10px;color:#a9f5d4;
        font-size:.7rem;font-weight:800;letter-spacing:.17em;margin-bottom:1.6rem}
    .brain-live {width:9px;height:9px;border-radius:50%;background:#69ffc1;
        box-shadow:0 0 0 5px #69ffc126,0 0 17px #2ff79c}
    .brain-heading {font-size:clamp(2.15rem,4.2vw,4.4rem);letter-spacing:-.065em;
        line-height:1.08;font-weight:900;color:#f6fff9;margin-bottom:1.1rem}
    .brain-heading span {color:#6af9b2}
    .brain-description {max-width:510px;font-size:clamp(.9rem,1.2vw,1.08rem);
        line-height:1.65;color:#c2dcd4}
    .brain-chips {margin-top:1.6rem;display:flex;flex-wrap:wrap;gap:8px}
    .brain-chips span {padding:8px 11px;background:#1245386c;border:1px solid #387d60;
        font-size:.65rem;letter-spacing:.12em;font-weight:800;border-radius:99px;color:#b3f6d6}
    .brain-art {position:absolute;right:1%;width:41%;height:340px;display:grid;place-items:center}
    .brain-art svg {position:relative;z-index:2;width:100%;height:100%;
        filter:drop-shadow(0 0 15px #52ffc447);animation:brain-breathe 5s ease-in-out infinite}
    .brain-orbit {position:absolute;width:72%;aspect-ratio:1;border:1px solid #63eac42f;
        border-radius:50%;transform:rotateX(64deg);animation:orbit-shift 9s ease-in-out infinite}
    .orbit-two {width:93%;animation-delay:-4s}
    @keyframes brain-breathe {0%,100%{transform:scale(.97)}50%{transform:scale(1.025)}}
    @keyframes orbit-shift {0%,100%{opacity:.3;transform:rotate(0deg) rotateX(64deg)}
        50%{opacity:.8;transform:rotate(35deg) rotateX(64deg)}}
    @media(max-width:720px) {
        .brain-command {min-height:420px;align-items:flex-start}
        .brain-copy {width:100%}
        .brain-art {width:84%;height:240px;right:-18%;top:190px;opacity:.50}
        .brain-chips {margin-top:1.1rem}
    }
    @media(prefers-reduced-motion:reduce) {.brain-art svg,.brain-orbit {animation:none}}

    .hero {position:relative; overflow:hidden; isolation:isolate}
    .hero:before {content:"";position:absolute;right:-8%;top:-90px;width:390px;height:390px;
        border-radius:50%;border:1px solid rgba(124,230,167,.27);
        box-shadow:0 0 0 24px rgba(124,230,167,.035),0 0 0 65px rgba(124,230,167,.025);
        animation:neuron-pulse 7s ease-in-out infinite;z-index:-1}
    .hero:after {content:"🧠";position:absolute;right:12%;top:20px;font-size:5.5rem;
        opacity:.25;filter:drop-shadow(0 0 20px #70de9f);
        animation:neuron-float 6s ease-in-out infinite;z-index:-1}
    [data-testid="stMetric"] {transition:transform .25s ease,border-color .25s ease}
    [data-testid="stMetric"]:hover {transform:translateY(-3px);border-color:#38ca85}
    @keyframes neuron-pulse {0%,100%{transform:scale(.98);opacity:.65}50%{transform:scale(1.08);opacity:1}}
    @keyframes neuron-float {0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
    @media (prefers-reduced-motion:reduce) {
        .hero:before,.hero:after {animation:none}
        [data-testid="stMetric"] {transition:none}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

render_brain_header()

analysis_tab, assistant_tab, simulator_tab, calendar_tab, context_tab, status_tab, parlays_tab, ledger_tab = st.tabs(
    ["🎯 Picks por partido", "🧠 Pregunta al asistente",
     "🎲 Simulaciones 10,000", "📅 Calendario",
     "🗞 Jugadores y noticias", "⚙️ Estado", "🧩 Parlays", "📊 Mi historial"]
)

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

with analysis_tab:
    render_morning_snapshot()
    st.divider()
    st.subheader("Ficha de picks · elige un partido")
    st.caption(
        "Escribe la liga, el equipo o un enfrentamiento. "
        "Consulta selecciones de referencia, momios y contexto del partido."
    )
    with st.form("sports_query"):
        prompt = st.text_input(
            "¿Qué partido, jugador o mercado quieres analizar?",
            value="Dame los partidos de NBA, NFL y NHL hoy",
            placeholder="Over de 24.5 puntos de Luka Doncic NBA hoy",
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
        st.info("Se vació la caché de Picks. La próxima consulta volverá a solicitar datos a las fuentes; si alguna falla, se indicará.")
    request = st.session_state.get("last_analysis_request")
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
        for league, link in links:
            try:
                covers = cached_covers(league, request.target_date)
            except (CoversSourceError, ValueError) as exc:
                st.warning(f"{league}: no fue posible actualizar los datos. Intenta nuevamente.")
                continue
            published.extend(covers["events"])
            st.caption(f"{league}: Actualizado {covers['checked_at_utc']} (UTC); "
                       f"fecha editorial {covers['page_date']}")
        from src.match_report import relevant_matches
        ranked, specific_request = relevant_matches(
            published, st.session_state.get("last_analysis_text", "")
        )
        if player_question:
            pass  # La consulta de jugador ya se respondió con evidencia ESPN.
        elif ranked:
            options = [
                f"{game['liga']} · {game['partido']} · {game['hora_cdmx']} CDMX"
                for game in ranked
            ]
            chosen = st.selectbox("Partido a analizar", options, key="selected_match")
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
            render_covers_evidence(game)
            from src.market_summary import game_market_probabilities
            market_p = game_market_probabilities(game)
            st.markdown("**Probabilidad implícita del moneyline (solo si hay momio real)**")
            if all(value is None for value in market_p.values()):
                st.caption("Sin moneyline verificable para ambos equipos; "
                           "no es posible calcular un umbral real de equilibrio. "
                           "Las proyecciones porcentuales no son momios.")
            else:
                p1, p2 = st.columns(2)
                if market_p["visitante"] is not None:
                    p1.metric("Visitante · umbral de equilibrio", f"{market_p['visitante']:.2f}%")
                if market_p["local"] is not None:
                    p2.metric("Local · umbral de equilibrio", f"{market_p['local']:.2f}%")
                st.caption("Calculado exclusivamente a partir del precio americano, con "
                           "posible margen del operador. NO es nuestra probabilidad de acierto.")
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
            st.markdown("**Dinero apostado, boletos y actividad de Las Vegas**")
            st.info(
                "Los porcentajes de consenso proceden de concursos "
                "gratuitos, no de dólares efectivamente apostados en casas de Las Vegas. "
                "No hay datos de dinero ni boletos reales verificados para este juego; "
                "no se inferirán a partir del consenso."
            )
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
            st.caption(
                "Las rachas completas de 5/10/15 partidos, estados médicos específicos "
                "y noticias de entrenadores requieren fuentes adicionales verificadas."
            )
            st.markdown("**Validación de Picks de Sports Edge AI**")
            st.caption("La selección de referencia anterior es únicamente una lectura del marcador "
                       "proyectado. Para validarla se requiere backtesting, "
                       "calibración y momios comparables de la misma fecha y mercado.")
            st.warning("PICKS PROPIOS PENDIENTES DE VALIDACIÓN. No se atribuye probabilidad, "
                       "EV, rentabilidad ni tamaño de apuesta a esta proyección externa.")
        else:
            if published and specific_request:
                st.warning(
                    "Los equipos solicitados no coinciden con los partidos publicados "
                    "para esta fecha. No mostraremos otro encuentro como si fuera el pedido."
                )
                st.dataframe(
                    [{"Liga": row["liga"], "Partido publicado": row["partido"],
                      "Hora CDMX": row["hora_cdmx"]} for row in published],
                    use_container_width=True, hide_index=True
                )
            else:
                st.warning(
                    "No se encontraron proyecciones extraíbles para esa fecha y ligas. "
                    "Esto no significa que no haya partidos. Consulta las fuentes originales."
                )
        if not player_question and ("ATP" in request.sports or "WTA" in request.sports):
            st.info("Los conectores de tenis ATP/WTA siguen pendientes de validación.")


with assistant_tab:
    from src.assistant_ui import render as render_assistant
    render_assistant(
        board_fetch=cached_scoreboard,
        covers_fetch=cached_covers,
        roster_fetch=cached_player_roster,
        gamelog_fetch=cached_player_gamelog,
        prop_odds_fetch=cached_prop_offers if safe_odds_key() else None,
        prop_api_key=safe_odds_key(),
    )

with simulator_tab:
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

with calendar_tab:
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

with context_tab:
    from src.news_ui import render as render_news
    render_news()


with status_tab:
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

with parlays_tab:
    from src.parlay_ui import render as render_parlay
    render_parlay()


with ledger_tab:
    from src.ledger_ui import render
    render()

