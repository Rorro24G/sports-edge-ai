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
            has_market = bool(item.get("market_price") and item.get("market_source"))
            cols = st.columns(3 if has_market else 2)
            cols[0].metric("Estimación experimental", f"{item['probability_experimental']:.1%}")
            cols[1].metric("Juegos ESPN analizados",
                           str(item["away_games"]) + " / " + str(item["home_games"]))
            if has_market:
                cols[2].metric("Momio externo verificable", item["market_price"])
            st.caption("Marcador estimado SEAI: "
                       + str(item["predicted_away"]) + " - "
                       + str(item["predicted_home"])
                       + " · forma reciente y defensa rival")
            if item.get("evidence"):
                with st.expander("Cómo razonó el cerebro", expanded=False):
                    st.markdown("**Pruebas independientes de la elección**")
                    for label, value in item["evidence"].items():
                        st.write(label + ": " + f"{value:+.2f}" +
                                 " puntos de margen local")
                    st.caption("Robustez de la elección: " +
                               f"{item.get('stability',0):.0%}" +
                               " en pruebas de sensibilidad. "
                               "No es una tasa de acierto.")
                    st.caption(item.get("reason", ""))
            if not compact:
                st.caption("Estimación NO calibrada; no es ventaja comprobada "
                           "ni recomendación de importe.")
            if item.get("espn_url", "").startswith("https://"):
                st.link_button("Datos ESPN", item["espn_url"])
            if item.get("market_source", "") and item["market_source"].startswith("https://"):
                st.link_button("Momios Covers", item["market_source"])
    elif status == "PASAR":
        st.caption("Sports Edge AI: PASAR. " + item.get("reason", "Señales contradictorias."))
    else:
        st.caption("Sports Edge AI: sin selección · " +
                   str(item.get("reason") or "sin datos suficientes"))


def render_own_slate(slate: dict) -> None:
    st.markdown("### Selecciones del cerebro")
    st.caption("Motor " + str(slate.get("model", VERSION)) +
               " · análisis independiente de resultados ESPN previos al partido.")
    candidates = slate.get("picks") or []
    if candidates:
        st.caption(str(len(candidates)) + " selecciones experimentales entre "
                   + str(len(slate.get("evaluated") or [])) + " partidos evaluados.")
        # Group the choices: raw confidence scores cannot rank different
        # sports against each other without cross-sport calibration.
        from .model_audit_ui import load_model_audits
        audits = load_model_audits()
        for league in ("NBA", "NFL", "NHL"):
            group = [item for item in candidates if item.get("sport") == league]
            if not group:
                continue
            st.markdown("#### " + league + " · señales propias")
            league_audits = [r for r in audits if r.get("sport") == league]
            if league_audits and any(
                r["validation_status"] == "MUESTRA_INSUFICIENTE"
                or r["brier_all_evaluated"] >= .25 for r in league_audits
            ):
                st.caption("La evidencia histórica de esta liga es limitada "
                           "o inconsistente entre temporadas. "
                           "Solo se muestran señales de investigación.")
            for item in group:
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
    st.caption("Selecciones ordenadas por liga, no como ranking global entre "
               "NBA, NFL y NHL. Probabilidades aún sin calibración final; "
               "sin importes de apuesta recomendados.")
