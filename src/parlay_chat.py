"""Conversación opcional de análisis de combinadas mediante Responses API.

Es una conversación independiente del chat de ChatGPT; no utiliza información
privada ni inventa cuotas. El dueño debe configurar un API key y modelo.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ParlayChatError(RuntimeError):
    pass


SYSTEM = (
    "Eres un asistente de revisión de apuestas deportivas en español. "
    "No tienes datos deportivos actuales ni cuotas en vivo a menos que el usuario "
    "proporcione los datos y sus fuentes explícitamente. No inventes partidos, "
    "momios, porcentajes de acierto, probabilidades propias ni garantías de "
    "ganancias. Si el usuario presenta una combinada, examina mercados, horarios, "
    "correlación entre selecciones, margen de las cuotas, posibles lesiones "
    "sin confirmar y motivos para evitar la jugada. "
    "Puedes discutir 2 o 3 BORRADORES de parlays basados en referencias externas "
    "con fuentes verificables. No los presentes como recomendaciones de apuestas "
    "de valor hasta que exista modelo propio validado. No rellenes cupos "
    "con selecciones inventadas. "
    "Un parlay normal no debe exceder 10 selecciones salvo petición explícita. "
    "Aclara que 1 selección es una apuesta simple, no un parlay. "
    "Nunca registres apuestas ni recomiendes una cantidad de dinero como certeza."
)


def ask_about_parlay(messages: list[dict], *, api_key: str, model: str) -> str:
    if not api_key or not model:
        raise ParlayChatError("Configura API y modelo para habilitar el chat IA")
    if not isinstance(messages, list) or not messages:
        raise ParlayChatError("Escribe una pregunta")
    # Sin herramientas, la IA no puede consultar cuotas actuales ni escribir historial.
    history = []
    for m in messages[-12:]:
        if m.get("role") not in ("user", "assistant"):
            continue
        content = m.get("content", "")
        if not isinstance(content, str) or len(content) > 3500:
            continue
        history.append({"role": m["role"], "content": content})
    if not history or history[-1]["role"] != "user":
        raise ParlayChatError("Falta tu pregunta")
    request = Request("https://api.openai.com/v1/responses",
                      data=json.dumps({
                          "model": model,
                          "instructions": SYSTEM,
                          "input": history,
                          "max_output_tokens": 850,
                          "store": False,
                      }, ensure_ascii=False).encode("utf-8"),
                      headers={
                          "Authorization": "Bearer " + api_key,
                          "Content-Type": "application/json",
                          "Accept": "application/json",
                      }, method="POST")
    try:
        with urlopen(request, timeout=35) as response:
            payload = response.read(500_001)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise ParlayChatError("Clave de API o acceso a modelo no autorizados") from None
        if exc.code == 429:
            raise ParlayChatError("Límite de consultas alcanzado") from None
        raise ParlayChatError("Servicio de IA no disponible (HTTP " + str(exc.code) + ")") from None
    except (URLError, TimeoutError, OSError):
        raise ParlayChatError("No se pudo consultar el servicio de IA") from None
    if len(payload) > 500_000:
        raise ParlayChatError("Respuesta de IA demasiado grande")
    try:
        response = json.loads(payload)
        parts = []
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for piece in item.get("content", []):
                if piece.get("type") == "output_text" and isinstance(piece.get("text"), str):
                    parts.append(piece["text"])
        answer = "\n".join(parts).strip()
        if not answer:
            raise ValueError()
        return answer[:5000]
    except (ValueError, TypeError, KeyError):
        raise ParlayChatError("La IA no devolvió texto interpretable") from None
