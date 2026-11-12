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
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """<section class="hero">
       <div class="eyebrow">SPORTS EDGE AI · CEREBRO DEPORTIVO</div>
       <div class="hero-title">Tu centro de análisis.</div>
       <p class="hero-sub">Pregunta por cualquier fecha y deporte. Consulta información trazable, simulaciones y riesgos en un solo lugar.</p>
    </section>""",
    unsafe_allow_html=True,
)

st.markdown(
    '<span class="status green">✓ Consulta de calendarios por fecha</span>'
    '<span class="status amber">◷ Momios de Covers consultados bajo demanda</span>'
    '<span class="status red">● Picks propios no validados</span>',
    unsafe_allow_html=True,
)

analysis_tab, simulator_tab, calendar_tab, context_tab, status_tab, parlays_tab = st.tabs(
    ["🎯 Picks por partido", "🎲 Simulaciones 10,000",
     "📅 Calendario", "🗞 Jugadores y noticias", "⚙️ Estado", "🧩 Parlays (último paso)"]
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

def safe_odds_key():
    try:
        return st.secrets.get("ODDS_API_KEY", "")
    except (FileNotFoundError, OSError):
        return ""

with analysis_tab:
    st.subheader("Ficha de picks · elige un partido")
    st.caption(
        "Escribe la liga, el equipo o un enfrentamiento. "
        "La información de Covers es externa; Sports Edge AI no presume tener un pick propio."
    )
    with st.form("sports_query"):
        prompt = st.text_input(
            "¿Qué partido quieres analizar?",
            value="Dame los partidos de NBA, NFL y NHL hoy",
            placeholder="Analiza Toronto contra Philadelphia hoy",
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
    request = st.session_state.get("last_analysis_request")
    if request is not None:
        st.caption("Fecha: " + request.target_date.strftime("%d/%m/%Y")
                   + " · Ligas: " + ", ".join(request.sports) + " · CDMX")
        links = picks_links(request.sports)
        published = []
        for league, link in links:
            try:
                covers = cached_covers(league, request.target_date)
            except (CoversSourceError, ValueError) as exc:
                st.warning(f"{league}: Covers no respondió con datos utilizables ({exc}).")
                st.link_button("Consultar " + league + " en Covers", link)
                continue
            published.extend(covers["events"])
            st.caption(f"{league}: Covers consultado {covers['checked_at_utc']} (UTC); "
                       f"fecha editorial {covers['page_date']}")
        if published:
            from src.match_report import rank_matches
            ranked = rank_matches(published, st.session_state.get("last_analysis_text", ""))
            options = [
                f"{game['liga']} · {game['partido']} · {game['hora_cdmx']} CDMX"
                for game in ranked
            ]
            chosen = st.selectbox("Partido a analizar", options, key="selected_match")
            game = ranked[options.index(chosen)]
            st.markdown("### " + game["partido"] + " · " + game["liga"])
            st.caption("Fecha " + game["fecha_cdmx"] + " · "
                       + game["hora_cdmx"] + " CDMX · Covers (información de terceros)")
            left, right = st.columns(2)
            left.metric("Proyección visitante · Covers",
                        str(game["proyeccion_visitante"])
                        if game["proyeccion_visitante"] is not None else "No disponible")
            right.metric("Proyección local · Covers",
                         str(game["proyeccion_local"])
                         if game["proyeccion_local"] is not None else "No disponible")
            st.markdown("**Mercados publicados por Covers**")
            st.write({
                "Moneyline visitante": game.get("momio_visitante") or "Sin momio verificable",
                "Moneyline local": game.get("momio_local") or "Sin momio verificable",
                "Over/under": game["totales_publicados"] or "Sin datos extraíbles",
                "Hándicaps": game["spreads_publicados"] or "Sin datos extraíbles",
                "Porcentajes de Covers": game["probabilidades_publicadas"] or "No publicados en esta ficha",
                "Tipo de cifras": game["tipo_mercados"],
            })
            st.link_button("Ver análisis original en Covers", game["fuente"])
            st.markdown("**Dinero apostado, boletos y actividad de Las Vegas**")
            st.info(
                "Los porcentajes de consenso de Covers proceden de sus concursos "
                "gratuitos, no de dólares efectivamente apostados en casas de Las Vegas. "
                "No hay datos de dinero ni boletos reales verificados para este juego; "
                "no se inferirán a partir del consenso."
            )
            consensus_url = consensus_link(game["liga"])
            if consensus_url:
                st.link_button("Ver consenso de " + game["liga"] + " en Covers",
                               consensus_url)
            st.link_button("Cómo calcula Covers el consenso",
                           PUBLIC_MONEY_EXPLANATION)
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
            st.caption(
                "Rachas de 5/10/15 juegos, noticias recientes de coaches, alineaciones "
                "confirmadas y estados médicos específicos siguen sin un conector verificado."
            )
            st.markdown("**Picks de Sports Edge AI**")
            st.warning(
                "Aún no hay picks propios respaldados por probabilidades calibradas, "
                "momios contrastados ni simulaciones ajustadas a datos reales. "
                "No se asignará ventaja ni tamaño de apuesta inventado."
            )
        else:
            st.warning(
                "No se encontraron proyecciones extraíbles para esa fecha y ligas. "
                "Esto no significa que no haya partidos. Consulta las fuentes originales."
            )
            for league, link in links:
                st.link_button("Picks de " + league + " en Covers", link)
        if "ATP" in request.sports or "WTA" in request.sports:
            st.info("Los conectores de tenis ATP/WTA siguen pendientes de validación.")

with simulator_tab:
    st.subheader("Laboratorio Monte Carlo")
    st.caption(
        "Puedes explorar 10,000 resultados hipotéticos de NBA o NFL. "
        "NO son predicciones reales: los parámetros deben ajustarse con datos previos al partido y validarse."
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
        run_sim = st.form_submit_button("Simular 10,000 veces", use_container_width=True)
    if run_sim:
        try:
            result = simulate_totals(GameScenario(
                sport=sport, away_mean=away_mean, home_mean=home_mean,
                away_sd=away_sd, home_sd=home_sd,
                score_correlation=correlation, total_line=line,
            ))
        except ValueError as exc:
            st.error(str(exc))
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Over simulado", f"{result.over_probability:.1%}")
            k2.metric("Under simulado", f"{result.under_probability:.1%}")
            k3.metric("Push simulado", f"{result.push_probability:.1%}")
            st.progress(result.over_probability)
            st.caption(
                f"Marcador total medio hipotético: {result.simulated_mean_total:.1f}. "
                f"Margen Monte Carlo 95% (solo muestreo): ±{result.over_mc_margin_95:.1%}. "
                "Este margen NO mide la incertidumbre del pronóstico ni prueba ventaja frente al mercado."
            )
            st.error(
                "ESCENARIO NO VALIDADO · No es un pick ni una señal para apostar. "
                "Faltan parámetros entrenados con datos reales, pruebas fuera de muestra y cuotas verificadas."
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
    st.subheader("Momentum y señales periodísticas")
    st.caption("Diseño del módulo de contexto; la ingesta automática todavía no está conectada.")
    st.markdown(
        "**Rendimiento reciente:** últimos juegos, volumen de uso, minutos, "
        "acarreos, recepciones, ritmo, descansos y cambios de rol.\n\n"
        "**Contexto:** lesiones, alineaciones, declaraciones de coaches, "
        "cambios tácticos y noticias en fuentes originales.\n\n"
        "**Redes sociales y pronosticadores:** publicaciones públicas de X y otras "
        "fuentes, con fecha y autor. Las afirmaciones no verificadas se mostrarán como rumores."
    )
    st.info(
        "Estas señales solo modificarán probabilidades cuando exista evidencia estadística "
        "de que mejoran los pronósticos. No se copiarán los supuestos porcentajes de acierto de terceros."
    )

with status_tab:
    st.subheader("Conexiones y seguridad")
    st.markdown(
        "- **GitHub:** código y pruebas versionados.\n"
        "- **Calendario:** consulta bajo demanda a ESPN de NBA, NFL y NHL; la fuente puede fallar.\n"
        "- **ATP/WTA:** proveedor de calendario por conectar.\n"
        "- **Momios:** The Odds API (moneyline, spread y totales), requiere ODDS_API_KEY.\n"
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
    st.subheader("Parlays · última etapa del proyecto")
    st.caption(
        "Primero deben funcionar las fichas por partido, las simulaciones "
        "y el calendario. Después evaluaremos combinaciones."
    )
    st.warning(
        "Todavía no hay parlays recomendados. Faltan probabilidades propias "
        "validadas, momios comprobados y estimación de dependencia entre selecciones. "
        "No multiplicaremos probabilidades independientes sin verificar esa condición."
    )
