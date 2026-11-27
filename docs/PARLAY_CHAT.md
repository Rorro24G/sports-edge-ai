# Conversación de Parlays en Sports Edge AI

El módulo permite fijar las preferencias del usuario: normalmente comparar 2 o 3 propuestas, máximo de 10 selecciones por parlay salvo autorización explícita para más, y no imponer un mínimo artificial de apuestas. Una sola selección es apuesta simple.

**Los parlays recomendados seguirán desactivados hasta disponer de un modelo predictivo propio validado, momios verificados y metodología para las dependencias entre selecciones.** Las solicitudes no se rellenan con picks inventados.

## Activar conversación IA dentro de Streamlit

En *Streamlit > App settings > Secrets*, añade (los valores son de ejemplo, no son claves reales):

```toml
OPENAI_API_KEY = "CLAVE_PRIVADA_DE_TU_PROYECTO_OPENAI"
PARLAY_CHAT_MODEL = "MODELO_HABILITADO_EN_TU_CUENTA_API"
```

El uso de la API se factura de forma independiente de ChatGPT. No muestres la clave en el chat, GitHub ni archivos de la app. La conversación de la pestaña ocurre en la API configurada, **no es el mismo hilo de esta conversación de ChatGPT**. Su estado permanece en la sesión actual de Streamlit, sin acceso automático a tu historial privado ni a cuotas en vivo. El modelo no puede hacer apuestas, modificar la base de datos ni obtener momios por sí solo: para analizar un parlay hay que proporcionarle los mercados y precios verificados o conectar una futura consulta segura.

Sin esos secretos, la pestaña ofrece enlace a ChatGPT para conversar manualmente. Si no hay evidencia de valor de los picks, el asistente debe explicar la incertidumbre en lugar de prometer rentabilidad.
