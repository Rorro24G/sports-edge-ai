"""Sports Edge AI: interfaz privada de laboratorio para consultas deportivas.

Ejecucion: pip install -r requirements-web.txt && streamlit run app.py
Aviso: este MVP NO publica picks, no opera apuestas ni contiene modelos validados.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from src.simulations import GameScenario, simulate_totals
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
    '<span class="status green">✓ Interfaz de prueba</span>'
    '<span class="status amber">◷ Calendario estático</span>'
    '<span class="status red">● Picks bloqueados: falta validación</span>',
    unsafe_allow_html=True,
)

analysis_tab, simulator_tab, context_tab, status_tab = st.tabs(
    ["🧠 Preguntar al cerebro", "🎲 Laboratorio 10,000 simulaciones",
     "🗞 Momentum y noticias", "⚙️ Estado del sistema"]
)

with analysis_tab:
    st.subheader("¿Qué quieres analizar?")
    st.caption("Escribe una fecha y los deportes. No necesitas elegir los partidos manualmente.")
    with st.form("sports_query"):
        prompt = st.text_input(
            "Tu consulta",
            value="Dame picks de NBA hoy",
            placeholder="¿Qué puedo apostar el 20 de noviembre en NFL, NBA y NHL?",
        )
        submitted = st.form_submit_button("Analizar partidos", use_container_width=True)
    try:
        request = interpret_request(prompt)
        fixture = load_fixture()
        schedule = find_games(fixture, request.target_date, request.sports)
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"No se pudo cargar el calendario: {exc}")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Fecha solicitada (CDMX)", request.target_date.strftime("%d/%m/%Y"))
        with col2:
            st.metric("Partidos en la copia", len(schedule.games))
        with col3:
            st.metric("Picks validados", "0")
        st.caption("Deportes solicitados: " + ", ".join(request.sports))
        if request.wants_picks:
            st.info("Estos son los partidos que tengo registrados; todavía no son picks. Para recomendar apuestas necesito cuotas vigentes y un modelo predictivo validado.")
        if not schedule.date_covered:
            st.warning(
                "La fecha solicitada está FUERA de la cobertura del calendario guardado. "
                "No significa que no haya partidos; hace falta conectar una fuente actualizada."
            )
        if schedule.missing_sports:
            st.info(
                "Aún no hay calendario conectado para: "
                + ", ".join(schedule.missing_sports)
                + ". No se inventarán enfrentamientos."
            )
        if schedule.games:
            st.subheader("Partidos encontrados")
            for match in schedule.games:
                with st.container(border=True):
                    left, right = st.columns([4, 1])
                    with left:
                        st.markdown(
                            f"**{match['sport']} · {match['away']} vs. {match['home']}**"
                        )
                        st.caption(
                            f"{match['local_time']} · hora Ciudad de México · "
                            f"{match['market_status']} · {match['prediction_status']}"
                        )
                    with right:
                        st.link_button("Fuente oficial", match["source_url"], use_container_width=True)
        elif schedule.date_covered and schedule.supported_sports:
            st.info("No se registraron encuentros de esos deportes y esa fecha en esta copia del calendario.")
        if request.wants_picks or request.wants_parlay:
            st.error(
                "No hay selecciones ni parlays verificables por ahora. "
                "Sin cuotas vigentes de TEAM MÉXICO ni modelos independientes calibrados, "
                "el tamaño recomendado de apuesta real es 0."
            )
        st.caption(
            fÚltima revisión de esta copia: {schedule.checked_date}. "
            "La aplicación aún no consulta automáticamente el calendario, cuotas, lesiones o resultados."
        )

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
        "- **Calendario:** copia local de NBA el 12 y de NBA, NFL y NHL del 13 al 15 de noviembre de 2026.\n"
        "- **ATP/WTA:** proveedor de calendario por conectar.\n"
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
