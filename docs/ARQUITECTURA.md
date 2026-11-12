# Arquitectura objetivo — Sports Edge AI

## Alcance

- NBA: moneyline, spread y total; lesiones, quintetos, ritmo, eficiencia y descanso.
- NFL: moneyline, spread y total; EPA/play, QB, plantillas, descanso, clima.
- NHL: moneyline, puck line y total; xG, porteros, línea, descanso.
- ATP/WTA: ganador de partido; Elo por superficie, servicio/devolución, forma y fatiga.
- No iniciar con apuestas en vivo, cuotas alternativas ni props sin disponer primero de históricos verificables.

## Diagrama

Proveedores (datos históricos, estadísticas, cuotas) -> adapters -> staging raw (inmutable + timestamps) -> normalización por evento/equipo/jugador -> features **point-in-time** -> modelos por deporte/mercado -> calibración -> comparación de mercado y riesgo -> simulación de parlays -> backtesting -> reportes Excel/Sheets.

## Tablas previstas

- `events`: event_id, sport, competition, start_utc, participant IDs, venue.
- `raw_odds`: event_id, observed_at_utc, book, market, selection, line, american_odds, source.
- `features`: event_id, as_of_utc, feature_version, feature names y valores.
- `predictions`: event_id, market_id, as_of_utc, model_version, p, lower, upper, calibration.
- `evaluations`: prediction_id, quoted_odds, implied_prob, expected_roi, uncertain_edge, eligible.
- `parlays`: component prediction IDs, joint-method, correlation audit, joint probability, payout, expected_roi.
- `results`: event outcome, grading rules, observed timestamp, ROI, CLV.

## Reglas estadísticas

- Evitar *data leakage*: ninguna variable con timestamp posterior a la decisión se usa en entrenamiento/backtest.
- División temporal rolling-forward, no particiones aleatorias que mezclen futuro y pasado.
- Comparar siempre contra baseline de mercado sin margen y demostrar mejora fuera de muestra.
- Brier score, log-loss y curvas de calibración por deporte/mercado; publicar tamaño de muestra.
- Históricos de cuotas a la misma hora de captura previa al evento; evitar backtesting con cuotas de cierre utilizadas ex-post.
- Incluir comisiones y las reglas de liquidación, pushes, retiros de tenis y mercados especiales.
- Si no hay evidencia suficiente, `SIN_RECOMENDACION`.
- No elevar una probabilidad al estatus de "37% comprobado" sin intervalos y calibración.
- Parlays de mismo evento: prohibidos hasta tener modelo conjunto. Deportes/eventos distintos tampoco implican independencia automática.

## Fases

**F0:** calcular y auditar odds; CSV y pruebas reproducibles (incluido).
**F1:** ingesta de estadística histórica por deporte y almacenamiento SQLite/Parquet/Postgres según volumen.
**F2:** modelos independientes y calibración con validación fuera de muestra.
**F3:** motor de parlays con simulaciones y dependencias.
**F4:** automatización, exportación Excel remota, alertas de calidad y control de costes.

## Elecciones de infraestructura

- GitHub privado + GitHub Actions puede ejecutar lotes programados; no sirve como proceso de tiempo real permanente y las ejecuciones pueden retrasarse.
- Para datos personales/credenciales usar secretos de GitHub Actions o servicio de secretos equivalente. Nunca en archivos versionados.
- Para escribir una hoja compartida de forma automática, usar una conexión autorizada con alcance mínimo; en caso de Excel en OneDrive, evaluar Graph con permisos limitados. No solicitar acceso a toda la cuenta.
- El CSV inicial es exportación interoperable con Excel sin credenciales adicionales.
