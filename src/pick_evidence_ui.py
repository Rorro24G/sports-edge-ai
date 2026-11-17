"""Visualización legible de Covers, Team México y ScoutPicks en Picks."""
from __future__ import annotations

import streamlit as st

from .pick_reference import covers_projection, TEAM_MEXICO_URL, SCOUT_PICKS_URL


def market_rows(game: dict) -> list[dict]:
    items = []
    for label, field in (
        ("Moneyline visitante", "momio_visitante"),
        ("Moneyline local", "momio_local"),
        ("Total (over / under)", "totales_publicados"),
        ("Hándicap / spread", "spreads_publicados"),
        ("Porcentajes publicados", "probabilidades_publicadas"),
    ):
        raw = game.get(field)
        values = [str(part).strip() for part in str(raw).split(",")] if raw else []
        for value in values:
            if not value:
                continue
            is_percentage = "%" in value
            if label.startswith("Moneyline"):
                kind = "Momio americano citado por Covers"
            elif label == "Porcentajes publicados":
                kind = "Porcentaje sin asignar a un mercado"
            elif is_percentage:
                kind = "Proyección porcentual, NO momio"
            else:
                kind = "Línea y precio citados por Covers"
            items.append({"Mercado": label, "Dato": value, "Interpretación": kind})
    return items


def render_covers_evidence(game: dict) -> None:
    st.markdown("**Selección de referencia · proyección externa**")
    signal = covers_projection(game)
    if signal is None:
        st.info("Covers no publicó un marcador proyectado suficiente para identificar "
                "un equipo favorito en este encuentro. No generaremos una selección artificial.")
    else:
        if not signal["vigente_para_analisis_prepartido"]:
            st.caption("Esta proyección corresponde a un encuentro que ya empezó "
                       "o está en el pasado. No constituye una selección para apostar ahora.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Equipo favorecido por Covers", signal["equipo_proyectado"])
        c2.metric("Margen de puntos proyectado", f"{signal['margen_proyectado']:.2f}")
        c3.metric("Total proyectado (puntos)", f"{signal['total_proyectado']:.2f}")
        st.caption("Referencia calculada del marcador proyectado por Covers: "
                   f"{signal['marcador_proyectado']} (visitante - local). "
                   "No equivale a un pick editorial de Covers, "
                   "ni a una probabilidad de victoria calibrada.")
        st.warning("SELECCIÓN NO VALIDADA PARA APUESTA: faltan momios confirmados, "
                   "comparación de probabilidades y pruebas históricas. "
                   "Sin EV propio ni porcentaje de bank recomendado para este juego.")
    st.markdown("**Mercados y porcentajes que realmente publicó Covers**")
    rows = market_rows(game)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Covers no ofreció cuotas o porcentajes legibles para estos mercados.")
    if game.get("tipo_mercados") == "proyecciones_porcentuales":
        st.info("IMPORTANTE: valores como «52%» son porcentajes publicados por Covers, "
                "no cuotas americanas ni porcentajes de dinero apostado. "
                "No pueden usarse para calcular el importe de una apuesta.")
    if not game.get("momio_visitante") or not game.get("momio_local"):
        st.caption("Moneyline incompleto: se deja vacío hasta obtener precios verificables "
                   "de ambos equipos. No se copiarán números de otro mercado.")


def render_extra_sources() -> None:
    st.markdown("**Conexiones adicionales solicitadas**")
    x, y = st.columns(2)
    with x:
        st.link_button("Consultar Team México", TEAM_MEXICO_URL)
        st.caption("Casa de apuestas: ofrece ganador, hándicap y totales; "
                   "no hemos obtenido aún una cotización automatizada y verificable "
                   "para este encuentro. El enlace no equivale a un momio conectado.")
    with y:
        st.link_button("Consultar ScoutPicks", SCOUT_PICKS_URL)
        st.caption("Plataforma de análisis enfocada principalmente en fútbol. "
                   "Su dashboard no proporciona por ahora un feed público verificado "
                   "de NBA/NFL/NHL a Sports Edge AI.")
