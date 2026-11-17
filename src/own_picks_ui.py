"""Streamlit cards for the independent Sports Edge AI research picks."""
from __future__ import annotations

import streamlit as st

from .independent_picks import VERSION


def render_own_result(item: dict, *, compact: bool = False) -> None:
    status = item.get("status")
    if status == "CANDIDATO_EXPERIMENTAL":
        with st.container(border=True):
            st.caption("SPORTS EDGE AI · SELECCIÓN PROPIA · EXPERIMENTAL")
            st.markdown("### " + item["team"] + " · Moneyline")
            p1, p2, p3 = st.columns(3)
            p1.metric("Estimación experimental", f"{item['probability_experimental']:.1%}")
            p2.metric("Momio publicado · Covers", item.get("market_price") or "—")
            p3.metric("Juegos ESPN analizados",
                      str(item["away_games"]) + " / " + str(item["home_games"]))
            if not compact:
                st.caption("Marcador estimado SEAI: "
                           + str(item["predicted_away"]) + " - "
                           + str(item["predicted_home"])
                           + " · ajuste de localía y forma reciente")
            st.caption("Estimación NO calibrada: no demuestra ventaja ni valor esperado. "
                       "Sin recomendación de importe.")
            if item.get("espn_url", "").startswith("https://"):
                st.link_button("Datos ESPN", item["espn_url"])
            if item.get("market_source", "") and item["market_source"].startswith("https://"):
                st.link_button("Momios Covers", item["market_source"])
    elif status == "PASAR":
        st.caption("Sports Edge AI: sin selección propia · el encuentro está demasiado equilibrado.")
    else:
        st.caption("Sports Edge AI: sin selección · " +
                   str(item.get("reason") or "sin datos suficientes"))


def render_own_slate(slate: dict) -> None:
    st.markdown("### Selecciones del cerebro")
    st.caption("Motor " + str(slate.get("model", VERSION)) +
               " · análisis de resultados ESPN previos al partido. "
               "Covers solo aporta precios.")
    candidates = slate.get("picks") or []
    if candidates:
        st.caption(str(len(candidates)) + " selecciones experimentales entre "
                   + str(len(slate.get("evaluated") or [])) + " partidos evaluados.")
        for item in candidates:
            render_own_result(item, compact=True)
    else:
        st.info("Hoy el cerebro no encontró partidos con historial y señal suficientes. "
                "No seleccionará a un favorito solo por sus momios.")
    evaluated = slate.get("evaluated") or []
    with st.expander("Partidos analizados por el cerebro", expanded=False):
        if evaluated:
            st.dataframe([{
                "Liga": x.get("sport", ""),
                "Partido": str(x.get("away", "")) + " vs " + str(x.get("home", "")),
                "Decisión SEAI": (x.get("team") if x.get("status") == "CANDIDATO_EXPERIMENTAL"
                                   else "Pasar"),
                "Motivo": x.get("reason", ""),
                "Estado": x.get("status", ""),
            } for x in evaluated], hide_index=True, use_container_width=True)
        else:
            st.caption("Sin encuentros prepartido verificables.")
    st.caption("No es un modelo entrenado y validado fuera de muestra. "
               "Las señales propias no constituyen apuestas recomendadas.")
