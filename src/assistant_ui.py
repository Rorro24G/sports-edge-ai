"""Chat privado de análisis con fuentes; sin credenciales ni servicios de IA."""
from __future__ import annotations

import streamlit as st

from .assistant_core import answer_query
from .brain_dashboard import load_today_snapshot


def render(*, board_fetch, covers_fetch, roster_fetch, gamelog_fetch) -> None:
    st.subheader("Asistente · pregunta por partidos y jugadores")
    st.caption(
        "Respuestas basadas en datos verificables de ESPN y Covers. "
        "Recuerda el jugador y la fecha durante esta sesión para preguntas de "
        "seguimiento. No es un modelo de lenguaje ni inventa momios."
    )
    examples = (
        "«Picks NBA hoy» · «Lakers contra Warriors» · "
        "«Over de 24.5 puntos de Luka Doncic NBA» · "
        "«¿Y el under de 27.5?» · «Dame 3 parlays de 2 selecciones»"
    )
    st.caption("Ejemplos: " + examples)
    history = st.session_state.setdefault("sports_assistant_history", [])
    ctx = st.session_state.setdefault("sports_assistant_context", {})
    if st.button("Nueva conversación", key="sports_assistant_clear"):
        history.clear()
        ctx.clear()
        st.rerun()

    for item in history[-14:]:
        with st.chat_message(item["role"]):
            st.write(item["text"])
            if item.get("sources") and item["role"] == "assistant":
                for index, url in enumerate(item["sources"][:4]):
                    st.link_button("Fuente " + str(index + 1), url)

    with st.form("sports_assistant_question_form", clear_on_submit=True):
        question = st.text_input(
            "Escribe tu pregunta", max_chars=1200,
            placeholder="¿Over de 24.5 puntos de Luka Doncic NBA hoy?",
        )
        asked = st.form_submit_button("Preguntar", use_container_width=True)

    if asked:
        if not question.strip():
            st.warning("Escribe una pregunta antes de enviarla.")
            return
        history.append({"role": "user", "text": question.strip()})
        with st.spinner("Contrastando la consulta con las fuentes disponibles..."):
            try:
                answer = answer_query(
                    question, context=ctx,
                    board_fetch=board_fetch, covers_fetch=covers_fetch,
                    roster_fetch=roster_fetch, gamelog_fetch=gamelog_fetch,
                    report_loader=load_today_snapshot,
                )
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                answer = {"reply": "No pude interpretar la consulta. Indica liga, "
                                   "jugador y línea cuando corresponda. "
                                   "Detalle: " + str(exc),
                          "sources": [], "context": ctx}
        st.session_state["sports_assistant_context"] = answer["context"]
        history.append({"role": "assistant", "text": answer["reply"],
                        "sources": answer.get("sources", [])})
        del history[:-14]
        st.rerun()
