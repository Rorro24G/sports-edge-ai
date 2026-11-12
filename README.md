# Sports Edge AI — base técnica revisada (12 nov 2026)

Proyecto privado para NBA, NFL, NHL y tenis ATP/WTA. Código Python 3.11+ sin dependencias externas para el calendario, matemáticas, datos de demostración y CSV. El modelo predictivo independiente **no existe todavía**; cualquier porcentaje calculado desde momios del mercado **no** es un pronóstico propio.

## Prueba viernes 13 y sábado 14 de noviembre de 2026

Calendario contrastado contra fuentes oficiales de NBA, NHL y NFL el 12 de noviembre de 2026. Son **30 partidos**: NBA 9 viernes + 5 sábado; NHL 2 viernes + 14 sábado; NFL 0 ambos días. Se incluyen 12 juegos de NFL del domingo 15 como extensión opcional. Los horarios se publican en Eastern y se convierten a America/Monterrey automáticamente.

```bash
python -m unittest discover -s tests -v
python -m src.weekend --start 2026-11-13 --end 2026-11-14
python -m src.weekend --start 2026-11-15 --end 2026-11-15 --sport NFL --output output/nfl_domingo.csv
```

El resultado `output/calendario_2026-11-13_14.csv` se puede importar en Excel y contiene una URL oficial por juego. En todos los registros el estado sigue siendo `SIN_CUOTAS_VERIFICADAS` y `SIN_MODELO_VALIDADO`: **no son recomendaciones de apuestas**. Actualizar los calendarios antes de cada jornada (son snapshots, no API en tiempo real).

## Datos de momios prepartido

La integración opcional con [The Odds API](https://the-odds-api.com/) consulta moneyline (h2h) para NBA, NFL, NHL y torneos de tenis disponibles. Necesita `ODDS_API_KEY`. Para no confundir cuotas con valor real, la comparación contra otras casas se etiqueta como **referencia de mercado**, no como predicción validada.

```bash
python -m src.pipeline --mode demo
# Requiere ODDS_API_KEY configurada en el entorno:
python -m src.pipeline --mode live --region us
```

No se ejecutan apuestas ni se accede a casas de apuestas. No se generan parlays por defecto: para ello necesitamos correlaciones estimadas, datos y validación fuera de muestra.

## Excel personal de OneDrive

Se puede exportar CSV ahora mismo. Se incluye un adaptador opcional para subir un archivo `.xlsx` completo con Microsoft Graph, **sin OAuth configurado ni ningún token almacenado**:

```bash
python -m src.onedrive_upload --file templates/Sports_Edge_AI_DEMO.xlsx --dry-run
```

Para el **mínimo permiso** en OneDrive personal diseñamos el destino `appfolder` con alcance delegado `Files.ReadWrite.AppFolder` de Microsoft Graph. El servicio puede crear una carpeta `Apps/{Nombre de la aplicación}`: no es la carpeta manual `Sports Edge AI` que el usuario ya creó. Si se insiste en la carpeta manual, sería necesario un alcance más amplio (`Files.ReadWrite`) y una decisión explícita. Ninguno se ha concedido; aún hace falta configurar autenticación OAuth y renovación segura para la automatización.

## GitHub Actions

`.github/workflows/mvp.yml` permite correr pruebas y exportación del calendario por petición manual (`Actions → Run workflow`, opción `calendar`) o elegir `demo`/`live`. No está activado el calendario automático ni la subida a OneDrive. La ejecución `live` solo funciona cuando se configura `ODDS_API_KEY` en los secretos del repositorio; no incluir credenciales en commits ni en un chat.

## Pasos siguientes

1. Verificar ejecución de CI del calendario y exportación en la pestaña Actions.
2. Seleccionar proveedor de momios, mercado/país y presupuesto de API.
3. Configurar autenticación OneDrive personal de alcance mínimo en Work; nunca compartir tokens o passwords por chat.
4. Obtener estadísticas históricas con fecha/hora de captura y entrenar modelos por deporte.
5. Calibrar fuera de muestra, medir Brier/log-loss y CLV; solo entonces habilitar evaluaciones y parlays.

Documentación: `docs/ARQUITECTURA.md`, `docs/ACCESOS.md`, `docs/ONEDRIVE.md`.
