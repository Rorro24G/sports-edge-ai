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
    """Compact, source-labelled Covers card without repetitive status banners."""
    st.markdown("#### Pick de referencia · Covers")
    signal = covers_projection(game)
    if signal is None:
        st.caption("Sin proyección de marcador verificable en Covers.")
    else:
        caption = ("Referencia prepartido" if signal["vigente_para_analisis_prepartido"]
                   else "Partido iniciado o finalizado · referencia histórica")
        with st.container(border=True):
            st.caption(caption)
            left, middle, right = st.columns([2, 1, 1])
            left.metric("Equipo favorecido por Covers", signal["equipo_proyectado"])
            middle.metric("Moneyline Covers", signal["momio_covers"] or "—")
            right.metric("Diferencia de puntos", f"{signal['margen_proyectado']:.2f}")
            st.caption("Marcador proyectado: " + signal["marcador_proyectado"]
                       + " · cálculo externo, no pick propio validado")

    st.markdown("#### Mercados disponibles")
    rows = market_rows(game)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Covers aún no publicó cuotas verificables.")
    st.caption("Precios de terceros sujetos a cambios. "
               "Los porcentajes de Covers no son moneyline ni dinero apostado.")
