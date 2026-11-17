"""Pestaña de discusión de parlays. Sin picks ficticios."""
from __future__ import annotations
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

from .brain_dashboard import load_today_snapshot
from .parlay_research import build_reference_parlays, parlay_review_prompt

from .parlay_chat import ask_about_parlay, ParlayChatError


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, OSError, KeyError):
        value = ""
    return str(value or os.getenv(name, ""))


def render() -> None:
    st.subheader("Parlays · planificación y discusión")
    st.caption("Normalmente se analizarán 2 o 3 combinaciones, máximo 10 "
               "selecciones por combinada salvo que tú pidas más.")
    c1, c2, c3 = st.columns(3)
    with c1:
        count = st.selectbox("Parlays que quieres comparar", [2, 3], index=1)
    with c2:
        allow_more = st.checkbox("Quiero más de 10 selecciones")
    with c3:
        requested_legs = st.number_input(
            "Selecciones por propuesta", min_value=1,
            max_value=30 if allow_more else 10, value=3, step=1,
            key="parlay_legs",
        )
    if requested_legs == 1:
        st.caption("Con una selección se trata de una apuesta simple, no de un parlay.")
    st.caption(
        "Las propuestas siguientes son BORRADORES para discutir, no picks propios "
        "validados, y las cuotas publicadas en Covers pueden proceder de varias casas."
    )
    now = datetime.now(ZoneInfo("America/Mexico_City"))
    report = load_today_snapshot(now.date())
    proposals = []
    if report:
        proposals = build_reference_parlays(
            report, count=count, legs_per_parlay=requested_legs,
            more_than_ten=allow_more, now=now,
        )
    st.markdown("**Combinadas de referencia · Covers + calendario confirmado por ESPN**")
    if not proposals:
        st.info(
            "No hay suficientes partidos futuros con proyección, moneyline en Covers "
            "y equipos contrastados en ESPN para crear propuestas ahora. "
            "No usaremos datos de ayer ni completaremos con partidos inventados."
        )
    else:
        for i, proposal in enumerate(proposals):
            with st.expander(
                proposal["nombre"] + " · " +
                str(proposal["num_selecciones"]) + " selecciones",
                expanded=(i == 0),
            ):
                st.dataframe([
                    {
                        "Liga": leg["liga"], "Partido": leg["evento"],
                        "Hora CDMX": leg["hora_cdmx"],
                        "Selección ML": leg["seleccion"],
                        "Momio Covers": leg["momio_covers"],
                        "Fuente": leg["fuente"],
                    } for leg in proposal["selecciones"]
                ], hide_index=True, use_container_width=True,
                    column_config={"Fuente": st.column_config.LinkColumn("Fuente Covers")})
                st.caption("Producto matemático de momios publicados: " +
                           proposal["cuota_decimal_teorica"] +
                           " decimal. NO es una cuota combinada ofrecida por una casa "
                           "y no puede usarse para inferir probabilidad o EV.")
                st.warning("Correlaciones NO evaluadas, cambios de precio posibles "
                           "y no existe una estimación propia calibrada. "
                           "Revisa cada selección antes de decidir.")
                if st.button("Preparar esta combinación para discutir",
                             key="discutir_parlay_" + str(i)):
                    st.session_state["parlay_chat_question"] = parlay_review_prompt(proposal)
                    st.rerun()
    st.caption("Pedir más de diez selecciones es posible únicamente al activar "
               "la opción correspondiente; si no existen partidos suficientes "
               "se mostrará una propuesta más corta, nunca apuestas ficticias.")
    st.markdown("**Discute un parlay antes de decidir**")
    st.caption("Puedes cuestionar correlaciones, revisar momios y compartir selecciones "
               "que quieras comparar. Las respuestas de IA no ejecutan apuestas ni "
               "las guardan automáticamente en tu historial.")
    key = _secret("OPENAI_API_KEY")
    model = _secret("PARLAY_CHAT_MODEL")
    if not (key and model):
        st.caption("Puedes copiar el borrador y debatirlo conmigo en ChatGPT. "
                   "Esta conversación de Streamlit no está conectada directamente a la de aquí.")
        draft = st.session_state.get("parlay_chat_question", "")
        if draft:
            st.code(draft, language="text")
        else:
            st.info("Selecciona «Preparar esta combinación para discutir» "
                    "o escribe tus selecciones para revisarlas en ChatGPT.")
        st.link_button("Abrir ChatGPT para discutir parlays", "https://chatgpt.com/")
        return
    history = st.session_state.setdefault("parlay_chat_history", [])
    if st.button("Borrar conversación de esta sesión", key="clear_parlay_chat"):
        history.clear()
        st.rerun()
    for item in history[-12:]:
        with st.chat_message(item["role"]):
            st.write(item["content"])
    question = st.text_area(
        "Tu pregunta para el asistente IA",
        key="parlay_chat_question",
        max_chars=2500,
        placeholder="¿Qué riesgo tendría combinar estos 3 picks a estos momios?",
    )
    if st.button("Enviar pregunta para discutir", key="parlay_send"):
        if not question.strip():
            st.warning("Escribe tu pregunta antes de enviarla")
            return
        proposed = (history + [{
            "role": "user",
            "content": question.strip() + "\n\n"
                       f"Preferencias: comparar {count} parlays y "
                       f"{requested_legs} selecciones por propuesta "
                       f"(más de 10: {'sí' if allow_more else 'no'}).",
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
