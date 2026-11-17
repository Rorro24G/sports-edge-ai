"""Streamlit smoke: conversational question + follow-up, no paid API."""
from streamlit.testing.v1 import AppTest

app = AppTest.from_file("../app.py", default_timeout=45).run()
assert not app.exception, [str(x.message) for x in app.exception]
inputs = [item for item in app.text_input if item.label == "Escribe tu pregunta"]
assert len(inputs) == 1, "Falta caja del asistente"
buttons = [b for b in app.button if b.label == "Preguntar"]
assert len(buttons) == 1, "Falta botón para hablar con asistente"
inputs[0].set_value("¿Qué puedes hacer?")
app = buttons[0].click().run()
assert not app.exception, [str(x.message) for x in app.exception]
first = app.session_state["sports_assistant_history"]
assert first[-1]["role"] == "assistant"
assert "Over de 24.5 puntos" in first[-1]["text"]
assert "Picks NBA hoy" in first[-1]["text"]
assert first[-1]["sources"] == []
inputs = [item for item in app.text_input if item.label == "Escribe tu pregunta"]
inputs[0].set_value("¿Cómo consulto mi bank?")
app = [b for b in app.button if b.label == "Preguntar"][0].click().run()
assert not app.exception, [str(x.message) for x in app.exception]
second = app.session_state["sports_assistant_history"]
assert "Mi historial" in second[-1]["text"]
assert "No tengo acceso a tu saldo" in second[-1]["text"]
assert len(second) == 4, "El bot debe recordar ambas interacciones"
print("STREAMLIT_NATURAL_ASSISTANT_UI_OK")
