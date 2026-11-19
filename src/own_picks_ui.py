"""Streamlit cards for the independent Sports Edge AI research picks."""
from __future__ import annotations

import streamlit as st

from .independent_picks import VERSION


def render_own_result(item: dict, *, compact: bool = False) -> None:
    status = item.get("status")
    if status == "CANDIDATO_EXPERIMENTAL":
        with st.container(border=True):
            st.caption(item.get("sport", "SEAI") + "  ·  PICK DEL CEREBRO")
            st.markdown("#### " + item["team"] + " · ML")
            has_market = bool(item.get("market_price") and item.get("market_source"))
            cols = st.columns(3 if has_market else 2)
            cols[0].metric("Estimación experimental", f"{item['probability_experimental']:.1%}")
            cols[1].metric("Juegos ESPN analizados",
                           str(item["away_games"]) + " / " + str(item["home_games"]))
            if has_market:
                cols[2].metric("Momio externo verificable", item["market_price"])
            st.caption(
                str(item.get("away", "")) + " vs " + str(item.get("home", ""))
                + " · Proyección " + str(item["predicted_away"]) + "–"
                + str(item["predicted_home"])
            )
            momentum = item.get("momentum") or {}
            away_m, home_m = momentum.get("away"), momentum.get("home")
            if away_m and home_m:
                st.caption(
                    "Momentum (últimos 3 vs 4 anteriores) · " +
                    str(item.get("away", "Visitante")) + " " +
                    f"{away_m['delta']:+.1f}" + " · " +
                    str(item.get("home", "Local")) + " " +
                    f"{home_m['delta']:+.1f}" + " puntos de margen"
                )
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
    st.markdown("### Picks para hoy")
    candidates = slate.get("picks") or []
    evaluated = slate.get("evaluated") or []
    overview = st.columns(2)
    overview[0].metric("Picks del cerebro", len(candidates))
    overview[1].metric("Partidos analizados", len(evaluated))
    source_status = slate.get("source_status") or {}
    unavailable = [
        sport for sport, status in source_status.items()
        if not status.get("available")
    ]
    if unavailable:
        st.warning(
            "ESPN no respondió para: " + ", ".join(unavailable) +
            ". Esas ligas no fueron evaluadas; no significa que no haya partidos."
        )
    if source_status:
        with st.expander("Estado de fuentes ESPN", expanded=False):
            cols = st.columns(3)
            for index, sport in enumerate(("NBA", "NFL", "NHL")):
                if sport not in source_status:
                    continue
                status = source_status[sport]
                cols[index].metric(
                    sport + " · calendario ESPN",
                    str(status.get("games", 0)) if status.get("available") else "Sin conexión",
                )
    if candidates:
        st.caption("Selecciones experimentales · forma ESPN · sin momios para elegir equipos")
        # Group the choices: raw confidence scores cannot rank different
        # sports against each other without cross-sport calibration.
        from .model_audit_ui import load_model_audits
        audits = load_model_audits()
        for league in ("NBA", "NFL", "NHL"):
            group = [item for item in candidates if item.get("sport") == league]
            if not group:
                continue
            st.markdown("#### " + league)
            league_audits = [r for r in audits if r.get("sport") == league]
            if league_audits and any(
                r["validation_status"] == "MUESTRA_INSUFICIENTE"
                or r["brier_all_evaluated"] >= .25 for r in league_audits
            ):
                st.caption("La evidencia histórica de esta liga es limitada "
                           "o inconsistente entre temporadas. "
                           "Solo se muestran señales de investigación.")
            for item in group[:3]:
                render_own_result(item, compact=True)
            if len(group) > 3:
                with st.expander(
                    "Ver " + str(len(group) - 3) + " picks más de " + league,
                    expanded=False,
                ):
                    for item in group[3:]:
                        render_own_result(item, compact=True)
    else:
        analyzed = slate.get("evaluated") or []
        if unavailable and not analyzed:
            st.error("No se pudieron evaluar partidos: fallaron las fuentes ESPN "
                     "seleccionadas. Reintenta la consulta cuando se restablezcan.")
        elif not analyzed:
            st.info("No hay encuentros futuros verificables en las ligas y fecha "
                    "solicitadas. Prueba otra fecha o liga.")
        else:
            st.info(
                "El cerebro revisó " + str(len(analyzed)) +
                " partidos pero ninguno pasó sus filtros. No fabricaremos "
                "selecciones usando favoritos ni cuotas Covers."
            )
    with st.expander("Ver todos los partidos y motivos del cerebro", expanded=False):
        if evaluated:
            from collections import Counter
            counts = Counter(str(x.get("status") or "SIN_DATOS") for x in evaluated)
            st.caption(
                "Decisiones · " +
                " · ".join(key + ": " + str(count) for key, count in sorted(counts.items()))
            )
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
    st.caption("Modelo experimental: probabilidades no calibradas. No hay importe recomendado.")
