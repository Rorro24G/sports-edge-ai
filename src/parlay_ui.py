"""Independent SEAI parlay research studio; ESPN decides, Covers only quotes."""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

# Legacy function remains for older reference-only reports, but it is NEVER
# used to decide the selections shown in the parlay studio.
from .brain_dashboard import load_today_snapshot
from .content_feed import live_parlay_report
from .independent_picks import add_covers_price
from .own_parlays import build_own_parlays, own_parlay_review_prompt
from .parlay_chat import ask_about_parlay, ParlayChatError

MX = ZoneInfo("America/Mexico_City")


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, OSError, KeyError):
        value = ""
    return str(value or os.getenv(name, ""))


@st.cache_data(ttl=600, show_spinner=False)
def cached_live_report(day):
    """Historical reference report, kept for existing integrations only."""
    return live_parlay_report(day)


def _enrich_prices(slate: dict, day, sports, covers_fetch) -> tuple[dict, list[str]]:
    """Price only after the sportsbook-independent slate is fully fixed."""
    if covers_fetch is None:
        return slate, []
    events, missing = [], []
    for sport in sports:
        try:
            data = covers_fetch(sport, day)
            events.extend(data.get("events", []))
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            missing.append(sport)
    priced = dict(slate)
    priced["picks"] = [
        add_covers_price(item, item, events, day)
        for item in slate.get("picks") or []
    ]
    return priced, missing


def _show_proposal(proposal: dict, index: int) -> None:
    with st.container(border=True):
        st.markdown("#### ◈ " + proposal["nombre"])
        st.caption(
            "SEAI · ESPN · " + str(proposal["num_selecciones"]) +
            " partidos distintos · selección experimental"
        )
        metrics = st.columns(2)
        metrics[0].metric("Piernas propias", proposal["num_selecciones"])
        metrics[1].metric(
            "Producto hipotético de momios",
            proposal["cuota_decimal_teorica"]
            if proposal["cuota_decimal_teorica"] else "Sin cuotas completas",
        )
        if proposal["incompleto"]:
            st.caption(
                "Solo había " + str(proposal["num_selecciones"]) +
                " selecciones verificables; pediste " +
                str(proposal["solicitadas"]) + ". No se agregaron picks de relleno."
            )
        st.dataframe([
            {
                "Liga": leg["liga"],
                "Partido ESPN": leg["evento"],
                "Hora CDMX": leg["hora_cdmx"],
                "SEAI eligió": leg["seleccion"] + " ML",
                "Momio Covers": leg["momio_covers"] or "—",
            }
            for leg in proposal["selecciones"]
        ], hide_index=True, use_container_width=True)
        with st.expander("¿Por qué eligió cada pierna?", expanded=False):
            for leg in proposal["selecciones"]:
                st.markdown(
                    "**" + leg["liga"] + " · " + leg["seleccion"] + "**"
                )
                if leg["robustez"] is not None:
                    st.caption(
                        "Robustez ante cambios de muestra: " +
                        f"{leg['robustez']:.0%}" +
                        " (no es probabilidad de ganar)."
                    )
                st.caption(leg["motivo"] or "Señal estadística prepartido de ESPN.")
                st.link_button("Ver encuentro ESPN", leg["fuente"])
                if leg["fuente_covers"]:
                    st.link_button("Ver momio Covers", leg["fuente_covers"])
        if not proposal["cuota_decimal_teorica"]:
            st.caption(
                "Sin precio combinado: faltan momios verificables. "
                "El cerebro mantiene sus selecciones igualmente."
            )
        else:
            st.caption(
                "Cuota decimal mostrada = producto de precios individuales. "
                "NO es una oferta real de una casa."
            )
        st.caption(
            "No se modeló correlación entre piernas ni probabilidad conjunta. "
            "No existe rentabilidad ni importe recomendados."
        )
        if st.button(
            "Preparar esta combinación para discutir",
            key="discutir_parlay_" + str(index), use_container_width=True,
        ):
            st.session_state["parlay_chat_question"] = own_parlay_review_prompt(proposal)
            st.rerun()


def _render_discussion(count: int, legs: int) -> None:
    st.markdown("### Mesa de revisión")
    st.caption(
        "Pregunta qué podría salir mal, revisa lesiones y fuentes. "
        "No se ejecutan apuestas ni se guardan en tu historial."
    )
    key = _secret("OPENAI_API_KEY")
    model = _secret("PARLAY_CHAT_MODEL")
    if not (key and model):
        draft = st.session_state.get("parlay_chat_question", "")
        if draft:
            with st.expander("Ver borrador listo para copiar", expanded=True):
                st.text_area(
                    "Resumen del análisis para compartir",
                    value=draft, height=230, key="parlay_share_draft"
                )
        else:
            st.info("Elige una combinación y pulsa «Preparar esta combinación "
                    "para discutir» para revisar sus riesgos.")
        st.link_button("Abrir ChatGPT para discutir", "https://chatgpt.com/")
        return

    history = st.session_state.setdefault("parlay_chat_history", [])
    if st.button("Borrar conversación de esta sesión", key="clear_parlay_chat"):
        history.clear()
        st.rerun()
    for message in history[-12:]:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    question = st.text_area(
        "Tu pregunta para el asistente IA",
        key="parlay_chat_question", max_chars=2500,
        placeholder="¿Qué riesgos tiene combinar estas dos selecciones?",
    )
    if st.button("Enviar pregunta para discutir", key="parlay_send"):
        if not question.strip():
            st.warning("Escribe una pregunta antes de enviarla")
            return
        proposed = (history + [{
            "role": "user",
            "content": question.strip() + "\n\nPreferencias: comparar " +
                       str(count) + " parlays de " + str(legs) + " selecciones.",
        }])[-12:]
        try:
            answer = ask_about_parlay(proposed, api_key=key, model=model)
        except ParlayChatError as exc:
            st.warning(str(exc))
            return
        history.append(proposed[-1])
        history.append({"role": "assistant", "content": answer})
        del history[:-12]
        st.rerun()


def render(*, slate_fetch=None, covers_fetch=None) -> None:
    st.markdown("### Parlays propios del cerebro")
    st.caption(
        "Elige primero Sports Edge AI usando resultados ESPN. "
        "Covers solo se consulta DESPUÉS para mostrar momios, si lo solicitas."
    )
    now = datetime.now(MX)
    first, second, third = st.columns(3)
    with first:
        count = st.selectbox(
            "Parlays que quieres comparar", [2, 3], index=1,
            key="seai_parlay_count"
        )
    with second:
        legs = st.number_input(
            "Selecciones por propuesta", min_value=2, max_value=10,
            value=2, step=1, key="parlay_legs"
        )
    with third:
        sports = st.multiselect(
            "Ligas para combinar", ["NBA", "NFL", "NHL"],
            default=["NBA", "NFL", "NHL"], key="seai_parlay_sports",
        )
    with st.container(border=True):
        add_prices = st.checkbox(
            "Consultar momios Covers (opcional; no cambian los picks)",
            value=False, key="seai_parlay_show_prices",
        )
        refreshed = st.button(
            "🧠 Generar / actualizar parlays propios",
            key="refresh_parlays", type="primary", use_container_width=True
        )
    if slate_fetch is None:
        st.warning("El analizador ESPN no está configurado en esta vista.")
        _render_discussion(count, legs)
        return
    if not sports:
        st.info("Selecciona al menos una liga para buscar picks propios.")
        _render_discussion(count, legs)
        return

    signature = (now.date().isoformat(), tuple(sports))
    existing = st.session_state.get("seai_parlay_slate")
    if refreshed:
        st.session_state.pop("seai_parlay_slate", None)
        clear = getattr(slate_fetch, "clear", None)
        if callable(clear):
            clear()
        existing = None

    if not existing or existing.get("signature") != signature:
        # Generate once on entry so the page has useful content immediately.
        with st.spinner("El cerebro revisa los partidos y resultados ESPN..."):
            try:
                analysis = slate_fetch(now.date(), tuple(sports))
            except (ValueError, OSError, RuntimeError, KeyError, TypeError):
                analysis = None
        if analysis is None:
            st.warning(
                "No fue posible analizar la jornada ESPN. "
                "Puedes volver a intentarlo con el botón de actualización."
            )
            _render_discussion(count, legs)
            return
        st.session_state["seai_parlay_slate"] = {
            "signature": signature, "value": analysis,
        }
        existing = st.session_state["seai_parlay_slate"]
    slate = existing["value"]

    if add_prices:
        with st.spinner("Buscando precios Covers, sin cambiar las elecciones..."):
            slate, price_errors = _enrich_prices(
                slate, now.date(), sports, covers_fetch
            )
        if price_errors:
            st.caption("Sin momios Covers para: " + ", ".join(price_errors))
    result = build_own_parlays(
        slate, now.date(), count=count, legs_per_parlay=int(legs), now=now,
    )
    stats = st.columns(3)
    stats[0].metric("Partidos elegibles", result["eligible_games"])
    stats[1].metric("Picks propios del cerebro", result["available"])
    stats[2].metric("Combinaciones distintas", len(result["proposals"]))
    if result["proposals"]:
        st.markdown("### Combinaciones generadas")
        st.caption(
            "Solo aparecen partidos que el modelo seleccionó de manera independiente. "
            "No mezclamos proyecciones de Covers ni obligamos al cerebro a elegir."
        )
        for i, proposal in enumerate(result["proposals"]):
            _show_proposal(proposal, i)
        if result["reason"]:
            st.info(result["reason"])
    else:
        st.info(result["reason"] or "No hay todavía dos selecciones propias "
                "entre los próximos partidos verificables.")
    with st.expander(
        "¿Qué analizó y por qué no salieron más parlays?",
        expanded=not bool(result["proposals"]),
    ):
        st.write(
            "ESPN: " + str(result["eligible_games"]) +
            " partidos futuros elegibles; " + str(result["evaluated"]) +
            " evaluados. Selecciones suficientes para combinar: " +
            str(result["available"]) + "."
        )
        excluded = result["excluded"]
        if excluded:
            st.dataframe([
                {"Decisión del cerebro": key, "Partidos": value}
                for key, value in sorted(excluded.items())
            ], hide_index=True, use_container_width=True)
        if result["available"] < 2:
            st.caption(
                "No se fabrican picks a partir de los favoritos del mercado. "
                "Prueba otra jornada o vuelve cuando ESPN publique más partidos."
            )
    st.caption(
        "Motor " + str(result["model"]) +
        ". Probabilidades individuales experimentales, sin calibración validada. "
        "Ninguna combinación representa una apuesta ofrecida o recomendada."
    )
    _render_discussion(count, legs)
