"""Visualización de referencias y momios publicados por Covers en Picks."""
from __future__ import annotations

import streamlit as st

from .pick_reference import covers_projection


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
                kind = "Momio americano publicado"
            elif label == "Porcentajes publicados":
                kind = "Porcentaje sin asignar a un mercado"
            elif is_percentage:
                kind = "Proyección porcentual, NO momio"
            else:
                kind = "Línea y precio publicados"
            items.append({"Mercado": label, "Dato": value, "Interpretación": kind})
    return items


def render_covers_evidence(game: dict) -> None:
    st.markdown("**Pick de referencia (pendiente de validación)**")
    signal = covers_projection(game)
    if signal is None:
        st.info("No hay un marcador proyectado suficiente para identificar "
                "un equipo favorito en este encuentro. No generaremos una selección artificial.")
    else:
        if not signal["vigente_para_analisis_prepartido"]:
            st.caption("Esta proyección corresponde a un encuentro que ya empezó "
                       "o está en el pasado. No constituye una selección para apostar ahora.")
        price = signal["momio_covers"] or "No publicado"
        st.markdown("**Selección de referencia: " + signal["seleccion_de_referencia"] +
                    " · Momio de referencia: " + price + "**")
        if not signal["vigente_para_analisis_prepartido"]:
            st.warning("Partido ya iniciado o pasado: esta selección es histórica, no una propuesta actual.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Equipo favorecido", signal["equipo_proyectado"])
        c2.metric("Margen de puntos proyectado", f"{signal['margen_proyectado']:.2f}")
        c3.metric("Total proyectado (puntos)", f"{signal['total_proyectado']:.2f}")
        st.caption("Referencia calculada del marcador proyectado: "
                   f"{signal['marcador_proyectado']} (visitante - local). "
                   "No equivale a una recomendación validada, "
                   "ni a una probabilidad de victoria calibrada.")
        st.caption("El moneyline indicado es una referencia, NO una consulta "
                   "actual a la casa. La referencia procede del marcador matemático, "
                   "no es necesariamente una recomendación editorial.")
        st.warning("SELECCIÓN DE REFERENCIA, NO PICK PROPIO VALIDADO: "
                   "sin backtesting, EV o porcentaje de bank sustentados.")
    st.markdown("**Mercados disponibles**")
    rows = market_rows(game)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No hay cuotas o porcentajes legibles para estos mercados.")
    if game.get("tipo_mercados") == "proyecciones_porcentuales":
        st.info("IMPORTANTE: valores como «52%» son porcentajes publicados, "
                "no cuotas americanas ni porcentajes de dinero apostado. "
                "No pueden usarse para calcular el importe de una apuesta.")
    if not game.get("momio_visitante") or not game.get("momio_local"):
        st.caption("Moneyline incompleto: se deja vacío hasta obtener precios verificables "
                   "de ambos equipos. No se copiarán números de otro mercado.")


