# Sports Edge AI — primera interfaz web (MVP)

## Estado real del proyecto (12 nov 2026)

Esta rama introduce la **primera interfaz** de Sports Edge AI con Streamlit.
El usuario puede escribir, por ejemplo:

- "Dame los picks de NBA y NHL del 13 de noviembre de 2026."
- "Quiero los partidos del 20 de noviembre en NFL y un parlay."
- "¿Qué hay de tenis mañana?"

La página detecta **fecha y deportes sin que el usuario tenga que enumerar partidos**.
Muestra partidos solo cuando están presentes en el calendario guardado y siempre
identifica **fuente y estado de validación**. Fuera del intervalo conocido, muestra
"sin cobertura", **no** "sin partidos".

### Ejecutar localmente

Desde la raíz del repositorio, con Python 3.11 o superior:

\`\`\`bash
python -m pip install -r requirements-web.txt
python -m unittest discover -s tests -v
streamlit run app.py
\`\`\`

Visitar la dirección local que Streamlit muestre en la terminal.
La web no se ha desplegado en ningún servidor y no tiene autenticación propia.

## Pantallas

1. **Preguntar al cerebro**: consulta libre, fecha local de México, filtros de
   deportes y calendario con enlace a la fuente. La copia actualmente cubre
   fechas ET 13 a 15 nov 2026 para NBA, NFL y NHL.
2. **Laboratorio Monte Carlo**: 10 000 escenarios NFL/NBA con parámetros
   hipotéticos editables. Marcador normal correlacionado; reporta over/under,
   pushes y margen de error por muestreo. **No es un modelo de predicción
   calibrado** y no evalúa precios reales.
3. **Momentum y noticias**: sección conceptual para estadísticas de forma,
   cambios de uso de jugadores, declaraciones de coaches, lesiones, noticias
   y publicaciones públicas en X, con distinción entre fuentes y rumores.
   Sin automatización de estas fuentes todavía.
4. **Estado**: muestra conexiones pendientes y advertencias de privacidad.

## Criterios de confianza antes de picks reales

- API legal y estable de calendario de NBA, NFL, NHL y ATP/WTA;
  cotejar horarios con zona America/Mexico_City.
- Datos históricos a fecha de partido y estatus de lesiones, rotaciones
  y cambios de uso sin fuga de información futura.
- Momios con marca temporal y mercado concretos, incluyendo verificación de
  cobertura de TEAM MÉXICO. No pedir credenciales de la casa de apuestas.
- Modelos entrenados y evaluados fuera de muestra por deporte y mercado:
  probabilidad calibrada, Brier, log loss, ROI con cuotas históricas y
  cierre de mercado. Simular 10 000 veces **no** demuestra exactitud.
- Solo después de medir incertidumbre se considerarán candidatos a picks.
  Gestión de riesgo con exposición cero cuando falten datos o ventaja verificada.
  Para parlays, incluir dependencia entre elecciones.

## Publicación segura

**NO desplegar la app públicamente todavía:** la versión actual no incluye
inicio de sesión. Para una web privada, utilizar autenticación administrada
por el proveedor de alojamiento y permitir solo la identidad autorizada;
evitar credenciales en GitHub o en el cliente. Hacen falta elección y permiso
limitado de hosting antes de publicar. La carpeta personal de OneDrive aún
no está sincronizada; no se necesita ese acceso para evaluar la interfaz.

## Mejoras siguientes

- Conector de calendario ATP/WTA y horarios locales.
- Ingesta de cuotas, noticias y momentum con citas y fecha verificable.
- Simulaciones basadas en modelos de puntos calibrados, no parámetros manuales.
- Resumen en lenguaje natural con picks y parlays **solo** donde exista
  evidencia cuantitativa de valor.
- Pruebas de seguridad, control de acceso, despliegue y sincronización OneDrive.
