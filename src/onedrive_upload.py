"""Carga controlada de un .xlsx a OneDrive usando Microsoft Graph.

Requiere un token OAuth DELEGADO válido en la variable MS_GRAPH_ACCESS_TOKEN.
El script no obtiene tokens ni persiste credenciales. Por defecto escribe
SOLO en la carpeta de aplicación: Files.ReadWrite.AppFolder. Para la carpeta
manual 'Sports Edge AI' haría falta un permiso delegado más amplio.

Prototipo sin conexión activa: utilice --dry-run para validar la ruta.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


TARGET_FOLDER = "Sports Edge AI"
GRAPH_BASE = "https://graph.microsoft.com/v1.0/me/drive/root:"
APP_FOLDER_BASE = "https://graph.microsoft.com/v1.0/me/drive/special/approot:"
MAX_SIMPLE_UPLOAD = 250 * 1024 * 1024


class OneDriveSyncError(RuntimeError):
    """Fallo de entrada o de sincronización; no incluye secretos en el mensaje."""


def target_url(filename: str, *, target: str = "appfolder") -> str:
    """Construye una ruta de archivo .xlsx sin aceptar traversal.

    target='appfolder' -> requiere Files.ReadWrite.AppFolder, recomendado.
    target='project_folder' -> requiere Files.ReadWrite (permiso más amplio).
    """
    if not filename or filename in (".", "..") or "/" in filename or "\\" in filename:
        raise OneDriveSyncError("El nombre del archivo debe ser simple, sin rutas.")
    if not filename.lower().endswith(".xlsx"):
        raise OneDriveSyncError("Por seguridad, solo se admiten archivos .xlsx.")
    if any(ord(c) < 32 for c in filename) or filename.startswith("."):
        raise OneDriveSyncError("El nombre de archivo no es válido.")
    part=quote(filename,safe='')
    if target == 'appfolder':
        return f'{APP_FOLDER_BASE}/{part}:/content'
    if target == 'project_folder':
        return f"{GRAPH_BASE}/{quote(TARGET_FOLDER, safe='')}/{part}:/content"
    raise OneDriveSyncError("Destino no reconocido")


def upload(file_path: Path, access_token: str, *, target: str = "appfolder") -> dict:
    if not file_path.is_file():
        raise OneDriveSyncError("El archivo de Excel indicado no existe.")
    if not access_token:
        raise OneDriveSyncError("Falta MS_GRAPH_ACCESS_TOKEN (OAuth delegado).")
    size = file_path.stat().st_size
    if size > MAX_SIMPLE_UPLOAD:
        raise OneDriveSyncError("El archivo supera el límite para subida simple.")
    url = target_url(file_path.name, target=target)
    request = Request(
        url,
        data=file_path.read_bytes(),
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        method="PUT",
    )
    try:
        with urlopen(request, timeout=45) as response:
            item = json.load(response)
    except HTTPError as exc:
        # No imprimir cuerpo de error completo ni token del proveedor.
        raise OneDriveSyncError(f"Microsoft Graph rechazó la carga: HTTP {exc.code}.") from None
    except URLError as exc:
        raise OneDriveSyncError("No se pudo conectar con Microsoft Graph.") from None
    return {"name": item.get("name"), "id": item.get("id"),
            "webUrl": item.get("webUrl"), "size": item.get("size")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Archivo .xlsx de origen")
    parser.add_argument("--dry-run", action="store_true", help="Validar sin conectarse")
    parser.add_argument("--target", choices=("appfolder", "project_folder"), default="appfolder",
                        help="appfolder usa alcance mínimo; project_folder exige acceso amplio")
    args = parser.parse_args()
    source = Path(args.file)
    if not source.is_file():
        parser.error("El archivo no existe")
    try:
        url = target_url(source.name, target=args.target)
        if args.dry_run:
            print(json.dumps({"mode": "dry-run", "file": str(source),
                              "destination": url,
                              "note": "No se enviaron archivos ni credenciales."},
                             ensure_ascii=False, indent=2))
            return
        result = upload(source, os.getenv("MS_GRAPH_ACCESS_TOKEN", ""), target=args.target)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except OneDriveSyncError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
