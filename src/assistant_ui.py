"""Chat privado de análisis con fuentes; sin credenciales ni servicios de IA."""
from __future__ import annotations

import streamlit as st

from .assistant_core import answer_query
from .brain_dashboard import load_today_snapshot
from .team_form import fetch_team_schedule


def render(*, board_fetch, covers_fetch, roster_fetch, gamelog_fetch,
           prop_odds_fetch=None, prop_api_key: str = "",
           team_fetch=fetch_team_schedule) -> None:
    st.markdown("### Conversa con el analista")
    st.caption("Pregunta por equipos, jugadores o la lógica detrás de los picks.")
    examples = (
        "«Picks NBA hoy» · «Lakers contra Warriors» · "
        "«Over de 24.5 puntos de Luka Doncic NBA» · "
        "«¿Y el under de 27.5?» · «¿Y las lesiones?» · «Dame 3 parlays de 2 selecciones» · "
        "«Noticias NBA» · «¿Qué tan confiable es tu modelo NBA?»"
    )
    history = st.session_state.setdefault("sports_assistant_history", [])
    if not history:
        st.caption("Ejemplos: «Picks NBA hoy» · «Lakers contra Warriors» · "
                   "«¿Qué tan confiable es el modelo?»")
        with st.expander("Más ideas para preguntar", expanded=False):
            st.caption(examples)
    ctx = st.session_state.setdefault("sports_assistant_context", {})
    if st.button("Nueva conversación", key="sports_assistant_clear"):
        history.clear()
        ctx.clear()
        st.rerun()

    for item in history[-14:]:
        with st.chat_message(item["role"]):
            st.write(item["text"])
            if item.get("sources") and item["role"] == "assistant":
                with st.expander("Consultar detalles"):
                    for index, url in enumerate(item["sources"][:4]):
                        st.link_button("Referencia " + str(index + 1), url)

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
                    team_fetch=team_fetch,
                    report_loader=load_today_snapshot,
                    prop_odds_fetch=prop_odds_fetch,
                    prop_api_key=prop_api_key,
                )
            except (ValueError, TypeError, KeyError, IndexError, OSError, RuntimeError):
                answer = {"reply": "No pude interpretar la consulta. Indica liga, "
                                   "jugador y línea cuando corresponda. Si la consulta era correcta, "
                                   "puede fallar la actualización de datos; intenta de nuevo.",
                          "sources": [], "context": ctx}
        st.session_state["sports_assistant_context"] = answer["context"]
        history.append({"role": "assistant", "text": answer["reply"],
                        "sources": answer.get("sources", [])})
        del history[:-14]
        st.rerun()

