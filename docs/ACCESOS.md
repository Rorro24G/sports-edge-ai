# Accesos mínimos que debe conceder el usuario

## GitHub

- Conectar GitHub a ChatGPT Work con permisos aprobados para un repositorio privado **específico** si la app admite alcance limitado.
- Crear repositorio privado `sports-edge-ai`. Evitar dar permisos de administración sobre toda la organización.
- Subir los archivos del proyecto. Inicialmente los permisos de GitHub Actions son `contents: read`.
- Almacenar la clave de The Odds API en Settings → Secrets and variables → Actions → New repository secret → `ODDS_API_KEY`.
- No enviar la API key por chat ni guardarla en `.env` versionado.

## The Odds API

- Cuenta separada con cuota ajustada a deportes/mercados/consultas.
- Elegir region/bookmakers basado en casas realmente disponibles para el usuario.
- Hacer una prueba de cobertura de NBA, NFL, NHL y tenis antes de asumir que habrá datos de todos.
- Registros de consumo y límites de gasto / peticiones.

## Excel

- MVP: importar CSV generado a Excel; ninguna autorización adicional.
- Automatización de la hoja: elegir Excel en OneDrive o Google Sheets y conectar solo el archivo/carpeta pertinente.
- No se necesita compartir una cuenta de casa de apuestas ni tarjeta bancaria.

## Decisiones pendientes

1. Casa(s) y región de cuotas: ¿de qué casa se deben comparar momios?
2. ¿Excel de escritorio/OneDrive o Google Sheets? Esto decide la API de escritura.
3. Presupuesto mensual de datos (incluyendo opción empezar con cero gasto).
4. Prepartido solamente (recomendado al comenzar) o también live (desaconsejado en F0).
5. Tenis: ATP y WTA individual; ¿incluir dobles/challengers más adelante?

## Derechos de datos

- Verificar términos, tasas, límites y derechos de redistribución de cada proveedor.
- No replicar datos de fuentes con uso restringido en un repositorio público.
