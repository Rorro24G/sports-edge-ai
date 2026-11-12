# OneDrive PERSONAL — estrategia de permisos mínimos

Estado: **no conectado**. `src/onedrive_upload.py` solo acepta un `MS_GRAPH_ACCESS_TOKEN` delegado ya obtenido de forma segura. `--dry-run` no envía datos ni se conecta.

## Opción recomendada: carpeta de la aplicación (App Folder)

- Registrar una aplicación Microsoft (Entra ID) que admita **cuentas personales**.
- Permiso delegado `Files.ReadWrite.AppFolder` (en Microsoft Graph puede figurar como *preview*).
- El acceso se limita a `/me/drive/special/approot`, normalmente `OneDrive/Apps/{Nombre aplicación}`. No equivale a la carpeta raíz `Sports Edge AI` creada manualmente.
- Con OAuth delegado, solicitar la mínima lista de ámbitos y evitar publicar el token o guardar secretos en el repositorio.
- Comando: `python -m src.onedrive_upload --file archivo.xlsx --target appfolder --dry-run`.

## Opción alternativa: carpeta manual ya creada

- Para acceder vía `/me/drive/root:/Sports Edge AI/archivo.xlsx:/content` se requeriría `Files.ReadWrite`, que puede alcanzar más archivos del usuario.
- No pedir ese ámbito de momento. `--target project_folder` existe solo para un caso autorizado explícitamente, no se usa de forma predeterminada.
- No confundir restringir la ruta en el script con restringir el alcance del token: **el permiso amplio sigue siendo amplio**.

## Automatización desatendida

Los tokens de acceso expiran. Para GitHub Actions programado haría falta un flujo OAuth compatible que renueve credenciales de manera segura, gestión de revocaciones y límites de acceso. **No está implementado**. Tampoco está conectado OneDrive a ChatGPT.

Fuentes:
- https://learn.microsoft.com/en-us/graph/onedrive-sharepoint-appfolder
- https://learn.microsoft.com/en-us/graph/api/drive-get-specialfolder?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/permissions-reference
