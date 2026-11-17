"""Pestaña de discusión de parlays. Sin picks ficticios."""
from __future__ import annotations
import os
import streamlit as st

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
    st.warning(
        "Aún no existe un conjunto de picks propios con valor estadístico validado "
        "para producir recomendaciones reales. La app no inventará 2 o 3 "
        "combinaciones solo para cumplir el número solicitado."
    )
    st.markdown("**Discute un parlay antes de decidir**")
    st.caption("Puedes cuestionar correlaciones, revisar momios y compartir selecciones "
               "que quieras comparar. Las respuestas de IA no ejecutan apuestas ni "
               "las guardan automáticamente en tu historial.")
    key = _secret("OPENAI_API_KEY")
    model = _secret("PARLAY_CHAT_MODEL")
    if not (key and model):
        st.info(
            "Chat IA en esta página pendiente de configuración: añade "
            "OPENAI_API_KEY y PARLAY_CHAT_MODEL en secretos de Streamlit. "
            "Mientras tanto puedes discutir cualquier parlay en este chat de ChatGPT."
        )
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
