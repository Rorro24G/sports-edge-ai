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
    """Covers is a SOURCE of markets, not the team selection algorithm."""
    st.markdown("#### Momios publicados por Covers")
    rows = market_rows(game)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No hay precios verificables para este encuentro.")
    st.caption("Valores sujetos a cambios. Los porcentajes de pronóstico "
               "no son momios americanos ni datos de dinero apostado.")
