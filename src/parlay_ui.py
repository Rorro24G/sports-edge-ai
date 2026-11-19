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
        add_covers_price(
            item,
            {
                "sport": item["sport"], "event_id": item["event_id"],
                "away": item["away"], "home": item["home"],
                "local_time": item["time"],
            },
            events, day,
        )
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
        if proposal["cuota_decimal_teorica"]:
            st.caption(str(proposal["num_selecciones"]) + " selecciones · Cuota de referencia "
                       + proposal["cuota_decimal_teorica"] + " (no ofrecida)")
        else:
            st.caption(str(proposal["num_selecciones"]) + " selecciones · Sin cuota verificada")
        for leg_index, leg in enumerate(proposal["selecciones"], 1):
            st.markdown("**" + str(leg_index) + ". " + leg["seleccion"] + " · ML**")
            st.caption(leg["liga"] + " · " + leg["evento"] + " · " + leg["hora_cdmx"] + " CDMX")
        if proposal["incompleto"]:
            st.caption("Se encontraron menos selecciones que las solicitadas. No se inventaron piernas.")
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
                st.link_button(
                    "ESPN · " + proposal["nombre"] + " · " + leg["seleccion"],
                    leg["fuente"],
                )
                if leg["fuente_covers"]:
                    st.link_button(
                        "Covers · " + proposal["nombre"] + " · " + leg["seleccion"],
                        leg["fuente_covers"],
                    )
        if st.button(
            "Preparar esta combinación para discutir",
            key="discutir_parlay_" + str(index), use_container_width=True,
        ):
            st.session_state["parlay_chat_question"] = own_parlay_review_prompt(proposal)
            st.rerun()


def _render_discussion(count: int, legs: int) -> None:
    key = _secret("OPENAI_API_KEY")
    model = _secret("PARLAY_CHAT_MODEL")
    if not st.session_state.get("parlay_chat_question") and not (key and model):
        return
    st.markdown("### Revisar combinación")
    if not (key and model):
        draft = st.session_state.get("parlay_chat_question", "")
        if draft:
            with st.expander("Ver borrador listo para copiar", expanded=True):
                st.text_area(
                    "Resumen del análisis para compartir",
                    value=draft, height=230, key="parlay_share_draft"
                )
        st.link_button("Abrir ChatGPT", "https://chatgpt.com/")
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
    st.caption("Combinaciones ESPN seleccionadas por el cerebro. Tú eliges cuántas comparar.")
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
    with st.expander("Opcional: consultar momios externos", expanded=False):
        add_prices = st.checkbox(
            "Consultar momios Covers (no cambia los picks)",
            value=False, key="seai_parlay_show_prices",
        )
    refreshed = st.button(
        "↻ Actualizar combinaciones",
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
    failures = slate.get("source_errors") or []
    if failures:
        st.warning(
            "Sin respuesta del calendario ESPN: " + ", ".join(failures) +
            ". Son ligas sin evaluar, NO ligas sin partidos."
        )
    stats = st.columns(2)
    stats[0].metric("Picks propios del cerebro", result["available"])
    stats[1].metric("Combinaciones distintas", len(result["proposals"]))
    if result["proposals"]:
        st.markdown("### Combinaciones generadas")
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
        rejected = [
            row for row in (slate.get("evaluated") or [])
            if isinstance(row, dict) and row.get("status") != "CANDIDATO_EXPERIMENTAL"
        ]
        if rejected:
            st.markdown("**Por qué descartó cada partido**")
            st.dataframe([
                {
                    "Liga": row.get("sport", ""),
                    "Partido": str(row.get("away", "")) + " vs " + str(row.get("home", "")),
                    "Decisión": row.get("status", ""),
                    "Motivo": row.get("reason", "Sin explicación del proveedor"),
                }
                for row in rejected
            ], hide_index=True, use_container_width=True)
        if result["available"] < 2:
            st.caption(
                "No se fabrican picks a partir de los favoritos del mercado. "
                "Prueba otra jornada o vuelve cuando ESPN publique más partidos."
            )
    st.caption("Borradores experimentales · Sin probabilidades conjuntas ni apuesta ejecutada.")
    _render_discussion(count, legs)
