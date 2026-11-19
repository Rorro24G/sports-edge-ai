# Sports Edge AI — fuentes y plan de integración para picks (12-11-2026)

Objetivo: que el usuario escriba una fecha/deporte y el sistema muestre partidos, precios de mercado, probabilidades propias calibradas, splits de apuestas y evidencia de riesgo. Sin datos o sin validación, **no entregar picks accionables ni tamaños positivos de apuesta**.

## Fuentes identificadas

| Capa | Fuente candidata | Qué aporta | Estado | Limitaciones |
|---|---|---|---|---|
| Momios / históricos | The Odds API: https://the-odds-api.com/liveapi/guides/v4/ | H2H, spreads, totals, múltiples casas y snapshots históricos en planes compatibles | Documentación pública identificada; sin clave, coste ni conexión comprobados | No promete TEAM MÉXICO; cobertura por deporte/casa |
| % de boletos y % del dinero | VSiN: https://vsin.com/betting-splits/ | Splits de DraftKings y Circa, historial de línea visual | Página pública identificada | No equivale a todo Las Vegas; reutilización automatizada requiere autorización/licencia |
| % apuestas y % dinero | Action Network: https://www.actionnetwork.com/public-betting | Splits y comportamiento del mercado | Página pública identificada | No asumir que hay API oficial de uso abierto ni derechos de redistribución |
| API de splits licenciable | Sportradar: https://developer.sportradar.com/insights/reference/betting-splits-faq | Ticket % y stake % en un producto comercial | Existe documentación y prueba mediante contacto comercial | Permisos de exposición restringidos; nº bruto de apuestas no publicable en el producto documentado |
| Consenso comunitario | Covers: https://contests.covers.com/consensus/faq | Picks de usuarios en concursos | Página pública identificada | No son apuestas reales en casas ni un proxy válido de dinero |
| Casa del usuario | TEAM MÉXICO | Precios finales que el usuario podría obtener | Sin integración pública verificada | No pedir acceso a su cuenta ni credenciales |

## Modelo de datos común

Por evento y mercado: `sport`, `event_id`, `market` (moneyline/spread/total), `selection`, `line`, `american_odds`, `book`, `captured_at_utc`, `source_url`, `source_license`, `is_stale`, `tickets_pct`, `handle_pct`, `split_book`, `model_probability`, `model_validation_status`, `expected_value`, `risk_status`. Cualquier dato ausente es `null`, nunca cero inventado.

## Plan

1. Validar en cuenta de prueba la cobertura/coste del proveedor de momios para NFL, NBA, NHL y ATP/WTA; no contratar sin aceptación del usuario.
2. Conservar snapshots de precios con marca temporal y metadatos de origen. Comprobar términos y licencia para ingesta y visualización.
3. Usar VSiN/Action Network como contraste manual al principio; para automatización sostenida solicitar acceso/permiso a la API de splits de Sportradar o licenciamiento alternativo. No sortear muros de pago, autenticación ni controles técnicos.
4. Incorporar estadísticas, lesiones, cambios de uso, declaraciones y noticias solo como variables fechadas y con trazabilidad; entrenar fuera de muestra sin fuga temporal.
5. Simulaciones NFL/NBA calibradas en los datos; comparar probabilidades con cuotas y medir Brier/log loss, calibración, retorno histórico y closing-line value. Los splits por sí solos no constituyen predicciones.
6. Exhibir en la web semáforo verde/rojo solo cuando estén verificadas cuotas, probabilidad y ventaja conservadora. De lo contrario mostrar "sin datos suficientes" y exposición cero.

## Permisos mínimos pendientes

No se necesita usuario ni contraseña de TEAM MÉXICO. El siguiente acceso técnico eventual es una clave **de lectura** para el proveedor de cuotas elegido, almacenada como secreto del servidor/GitHub Actions, sin compartirla en chat. Para porcentajes reales de dinero y boletos de manera automatizada se necesitaría licencia o prueba de un proveedor de splits. No hay conexiones de cuotas ni splits activas a 12-11-2026.
