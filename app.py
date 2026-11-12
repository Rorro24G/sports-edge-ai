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
    '<span class="status amber">◷ Momios requieren fuente autorizada</span>'
    '<span class="status red">● Picks propios no validados</span>',
    unsafe_allow_html=True,
)

analysis_tab, simulator_tab, context_tab, status_tab = st.tabs(
    ["🧠 Preguntar al cerebro", "🎲 Laboratorio 10,000 simulaciones",
     "🗞 Momentum y noticias", "⚙️ Estado del sistema"]
)

@st.cache_data(ttl=600, show_spinner=False)
def cached_scoreboard(sport, target):
    return fetch_scoreboard(sport, target)

@st.cache_data(ttl=300, show_spinner=False)
def cached_odds(key, sports, target):
    return odds_for_day(key, sports, target)

def safe_odds_key():
    try:
        return st.secrets.get("ODDS_API_KEY", "")
    except (FileNotFoundError, OSError):
        return ""

with analysis_tab:
    st.subheader("Partidos, momios y fuentes")
    st.caption("Escribe tu pregunta y consulta datos del día, sin calendarios fijos. Zona horaria: Ciudad de México.")
    with st.form("sports_query"):
        prompt = st.text_input(
            "Tu consulta",
            value="Dame picks de NBA, NFL y NHL hoy",
            placeholder="¿Qué partidos y momios hay hoy en NBA, NFL y NHL?",
        )
        submitted = st.form_submit_button("Consultar partidos de hoy", use_container_width=True)
    if submitted:
        try:
            request = interpret_request(prompt)
        except (ValueError, TypeError) as exc:
            st.error("Fecha solicitada no válida: " + str(exc))
        else:
            cols = st.columns(3)
            cols[0].metric("Fecha (CDMX)", request.target_date.strftime("%d/%m/%Y"))
            selected_sports = tuple(s for s in request.sports if s in ("NBA", "NFL", "NHL"))
            cols[1].metric("Ligas conectadas", len(selected_sports))
            cols[2].metric("Picks independientes validados", "0")
            st.caption("Solicitado: " + ", ".join(request.sports))
            if not selected_sports:
                st.warning("La conexión de calendario para tenis ATP/WTA aún está pendiente.")
            all_games = []
            for league in selected_sports:
                try:
                    board = cached_scoreboard(league, request.target_date)
                except CalendarSourceError:
                    st.warning("No se pudo actualizar el calendario de " + league + ". No mostraré una copia vieja como si fuera de hoy.")
                    continue
                games = board["games"]
                all_games.extend(games)
                st.caption(league + ": consultado en " + board["source"] + " · " + board["checked_at_utc"] + " (UTC)")
                if not games:
                    st.info("No se encontraron partidos de " + league + " en la fecha solicitada.")
            if all_games:
                st.subheader("Partidos encontrados · hora Ciudad de México")
                for match in sorted(all_games, key=lambda x: (x["local_time"], x["sport"])):
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        c1.markdown(f"**{match['sport']} · {match['away']} vs. {match['home']}**")
                        c1.caption(match["local_time"] + " CDMX · " + match["status"] + " · fuente: " + match["source_name"])
                        c2.link_button("Ver fuente", match["source_url"], use_container_width=True)
            st.subheader("Momios de casas de apuestas")
            api_key = safe_odds_key()
            if not api_key:
                st.info("Fuente de momios aún no activada. Al añadir ODDS_API_KEY en los secretos privados de Streamlit aparecerán moneyline, spread y totales de las casas disponibles. No se inventan cuotas ni se piden contraseñas.")
            elif selected_sports:
                try:
                    rows = cached_odds(api_key, selected_sports, request.target_date)
                except (OddsAPIError, ValueError) as exc:
                    st.warning("No se pudieron obtener momios: " + str(exc))
                else:
                    if rows:
                        st.dataframe(rows, use_container_width=True, hide_index=True)
                        st.caption("Momios prepartido en formato americano. Fuente: The Odds API; cada fila incluye casa y hora de actualización. No incluye necesariamente TEAM MÉXICO.")
                    else:
                        st.info("La fuente de cuotas no devolvió mercados prepartido para esa fecha y esas ligas.")
            st.subheader("Pronósticos de terceros y método")
            st.markdown("**Picks publicados por expertos de Covers** (enlaces al origen, no predicciones de nuestro modelo): [NBA](https://www.covers.com/picks/nba) · [NFL](https://www.covers.com/picks/nfl) · [NHL](https://www.covers.com/picks/nhl). No se importan ni se presentan como recomendaciones propias sin autorización de datos y verificación.")
            if "ATP" in request.sports or "WTA" in request.sports:
                st.info("Tenis ATP/WTA: fuente de calendarios, momios y análisis aún sin validar.")
            if request.wants_picks or request.wants_parlay:
                st.warning("Las predicciones de Covers no son picks generados por nuestra IA. No hay recomendaciones de apuestas propias hasta entrenar y validar probabilidades con resultados históricos. Tamaño de apuesta recomendado actualmente: 0.")

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
        "- **Covers:** pronósticos de expertos NBA/NFL/NHL por referencia, no copiados automáticamente.\n"
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
