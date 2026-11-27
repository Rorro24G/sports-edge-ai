# Sports Edge AI — publicación privada de primera versión

**Estado a 12 de noviembre de 2026:** este repositorio aún no tiene un enlace web desplegado. El código de la aplicación está en la rama `feature/web-mvp-2026-11-12`; `app.py` es la entrada de Streamlit. El diseño inmersivo alternativo `web/brain_v2.html` es una maqueta visual y todavía no está integrado con el motor de Streamlit.

## Prueba privada en Streamlit Community Cloud

La documentación oficial https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app indica que una aplicación desplegada desde un repositorio privado hereda privacidad del repositorio y que se puede restringir su visualización a personas invitadas. Se permite una aplicación privada por cuenta de Community Cloud (según docs consultadas el 12/11/2026).

1. El titular del repositorio accede a https://share.streamlit.io e inicia sesión con GitHub.
2. Conecta GitHub **solo con el acceso a repositorio necesario**, según las opciones ofrecidas por GitHub/Streamlit. Confirma que el repositorio privado `Rorro24G/sports-edge-ai` esté disponible.
3. En **Create app**, elegir repo `Rorro24G/sports-edge-ai`, rama `feature/web-mvp-2026-11-12`, entrada `app.py`. El archivo estándar `requirements.txt` declara la dependencia.
4. Confirmar en Sharing la opción **Only specific people can view this app** y no hacerla pública.
5. Probar desde una sesión autenticada el panel de consultas, calendario 13–15 de noviembre y laboratorio hipotético.

**No se debe publicar ni afirmar un dominio hasta que un despliegue real devuelva una URL comprobada.** No se deben introducir contraseñas ni claves de casas de apuestas en GitHub o el chat.

## Antes de considerar el sistema terminado

- Integrar la portada/cerebro interactivo con las rutas de análisis del servidor.
- Añadir calendario actualizado NBA/NFL/NHL/ATP/WTA y capturar hora local del usuario.
- Conectar fuentes de momios y de estadísticas históricas (con permisos y límites de uso), sin depender de la cuenta de TEAM MÉXICO.
- Construir, calibrar y validar modelos con datos anteriores a cada evento. Un simulador de 10,000 escenarios hipotéticos NO demuestra que existan picks ganadores.
- Añadir trazabilidad de noticias, momentum, lesiones y porcentaje de apuestas/dinero cuando el proveedor ofrezca legalmente esos datos.
- Controlar incertidumbre y riesgo, historial y sincronización OneDrive opcional.
- Probar autenticación y uso en celular antes de entregar como "terminado".

Esta guía prepara el **despliegue privado del MVP**, no certifica que el sistema completo esté terminado.
