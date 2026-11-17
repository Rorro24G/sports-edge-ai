# Configurar «Mi historial» (privado)

Se agregó una última pestaña a Sports Edge AI que permite registrar **solo apuestas que tú confirmas** con instrucciones en español, calcular tu bank, resultados y exportar Excel/CSV y JSON. El historial empieza vacío. No inventa resultados ni transforma picks públicos de Covers en apuestas tuyas.

## Seguridad y almacenamiento

## Opción recomendada: guardar en GitHub PRIVADO

La app admite un repositorio **privado dedicado** como almacenamiento duradero, sin depender del disco temporal de Streamlit. Crea un repositorio privado vacío (por ejemplo, `tu-usuario/historial-picks-privado`). Después crea en GitHub un *fine-grained personal access token* limitado **solo** a ese repositorio, con permiso de lectura y escritura de contenido. No pegues el token en el chat ni en ningún fichero del repositorio.

En **Streamlit > App settings > Secrets** configura:

```toml
LEDGER_ACCESS_PASSWORD = "UNA_CONTRASEÑA_PRIVADA_Y_LARGA"
LEDGER_GITHUB_REPO = "tu-usuario/historial-picks-privado"
LEDGER_GITHUB_TOKEN = "TOKEN_PRIVADO_PONLO_AQUI_EN_SECRETS"
LEDGER_GITHUB_BRANCH = "main"
LEDGER_GITHUB_PATH = "private/historial.json"
```

El repositorio debe permanecer privado; el sistema **rechaza repositorios públicos**. Cada modificación se guarda con control de versión por SHA y no sobrescribe silenciosamente cambios de otra sesión. Los archivos quedan en el historial Git del repositorio privado, por lo que solo deben tener acceso las personas autorizadas. Protege también la aplicación publicada con acceso privado; una única contraseña compartida de la pestaña no sustituye autenticación personal si amplías el proyecto a varios usuarios.

Como alternativa a GitHub privado, puedes establecer estos secretos en **Streamlit > App settings > Secrets**:

```toml
LEDGER_ACCESS_PASSWORD = "CONTRASEÑA_LARGA_GENERADA_POR_TI"
LEDGER_DB_PATH = "/RUTA/REAL/A/UN/VOLUMEN/PERSISTENTE/historial.sqlite"
```

**Importante:** el almacenamiento local de Streamlit Community Cloud normalmente no persiste al reiniciar la instancia. Si no tienes un volumen persistente conectado, **no configures una ruta temporal pensando que conservará tu dinero y tu historial**. La aplicación bloquea la edición de historial cuando falta la configuración. Nunca subas una contraseña, token o el fichero SQLite a GitHub. La copia JSON descargable es manual y contiene datos personales: guárdala en un lugar privado.

Si utilizas SQLite, la carpeta del fichero debe existir o ser creable por el proceso de Streamlit, tener permisos apropiados y sobrevivir reinicios y redeploys. **En Streamlit Community Cloud, el repositorio GitHub privado es la opción de persistencia disponible en este código**; hay que configurarlo con tu token personal y comprobarlo en la aplicación desplegada. SQLite es adecuado para un usuario con escritor único; si la app va a ser multiusuario, habrá que separar cuentas y permisos mediante un backend autenticado real.

## Entrada por texto

Ejemplo:

> Voy a meter NBA, partido: Lakers vs Warriors; pick: Lakers ML; momio: -110; con $100

La app enseña un borrador y solicita pulsar **Confirmar y guardar apuesta**; no intenta apostar por ti. Puedes elegir fecha. Para evitar errores, cada comando registra una selección. En una siguiente versión se podrá crear un boleto combinado con varias selecciones.

Resultados: ganador, perdedor, push, anulado. El módulo puede proponer resultados de moneyline usando ESPN para partidos terminados, pero exige que revises y confirmes el marcador antes de liquidarlos. Los mercados de spread, total, props y parlays requieren validación específica y no se califican por adivinación.

## Indicadores

- Bank inicial, bank actual (beneficios y pérdidas realizados), disponible tras stakes pendientes.
- Porcentaje del bank utilizado en el momento de registrar cada apuesta.
- Referencia del 5% del disponible, **no una instrucción para apostar**.
- Ganadas, perdidas, pushes, anuladas y pendientes.
- Porcentaje de acierto = ganadas / (ganadas + perdidas) de apuestas liquidadas. Los pushes no cuentan como victorias.
- ROI = beneficio neto / total apostado en selecciones liquidadas (ganadas y perdidas).
- Rentabilidad sobre bank inicial = beneficio neto / bank inicial.
- Exportación CSV para Excel y copia completa JSON para restaurar en una instalación vacía.

El motor de Picks de Sports Edge AI sigue **sin probabilidad propia validada**. Estos datos miden apuestas que el usuario reporta, no su rentabilidad futura.

## Parlays

Requisito funcional pendiente para la fase de parlays: mostrar 2–3 sugerencias **solo cuando existan picks propios con valor respaldado**, máximo normal 10 selecciones por boleto (ampliable si lo solicitas), sin mínimo de selecciones, y permitir discutir cada recomendación antes de agregarla a tu historial. No se generarán parlays ficticios para llenar un cupo.
