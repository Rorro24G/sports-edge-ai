"""Almacenamiento duradero opcional del historial en un repositorio GitHub PRIVADO.

El token de contenido se configura solo como secreto en Streamlit. Un fichero
JSON controlado por SHA evita sobrescribir cambios concurrentes silenciosamente.
Usar preferentemente OTRO repositorio privado dedicado al historial, no el
repositorio del código. NO almacena el token en archivos ni respuestas públicas.
"""
from __future__ import annotations

import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from typing import Callable, TypeVar

from .pick_ledger import LedgerError, new_ledger
from .ledger_store import validate_ledger, MAX_BYTES

T = TypeVar("T")
MAX_RESPONSE = 4_000_000
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,100}$")
_FILE = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.json$")


def _paths(repository: str, branch: str, path: str) -> tuple[str, str]:
    if not _REPO.fullmatch(repository) or ".." in repository:
        raise LedgerError("Nombre de repositorio GitHub inválido")
    if not _BRANCH.fullmatch(branch) or ".." in branch or "//" in branch:
        raise LedgerError("Rama GitHub inválida")
    if not _FILE.fullmatch(path) or ".." in path or path.startswith("/"):
        raise LedgerError("Ruta del historial inválida")
    base = "https://api.github.com/repos/" + repository
    file_url = base + "/contents/" + quote(path, safe="/")
    return base, file_url


def _api(url: str, token: str, *, data: dict | None = None) -> dict | None:
    if not token or len(token) < 20:
        raise LedgerError("Hace falta token privado de GitHub para guardar el historial")
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    request = Request(url, data=body, method="PUT" if data is not None else "GET",
                      headers={
                          "Authorization": "Bearer " + token,
                          "Accept": "application/vnd.github+json",
                          "User-Agent": "SportsEdgeAI-ledger-private/1.0",
                          "X-GitHub-Api-Version": "2022-11-28",
                          **({"Content-Type": "application/json"} if body is not None else {}),
                      })
    try:
        with urlopen(request, timeout=14) as response:
            payload = response.read(MAX_RESPONSE + 1)
    except HTTPError as exc:
        if exc.code == 404 and data is None:
            return None
        if exc.code in (409, 412, 422):
            raise LedgerError("El historial cambió en otro dispositivo; recarga antes de guardar") from None
        if exc.code in (401, 403):
            raise LedgerError("GitHub rechazó el acceso; revisa el token y sus permisos") from None
        raise LedgerError("GitHub no pudo atender la operación (HTTP " + str(exc.code) + ")") from None
    except (URLError, TimeoutError, OSError):
        raise LedgerError("GitHub no está disponible ahora; no se guardó el cambio") from None
    if len(payload) > MAX_RESPONSE:
        raise LedgerError("Respuesta GitHub demasiado grande")
    try:
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (ValueError, UnicodeDecodeError):
        raise LedgerError("Respuesta GitHub inválida") from None


def _check_private(repo_url: str, token: str) -> None:
    info = _api(repo_url, token)
    if info is None:
        raise LedgerError("No se encontró el repositorio con este token")
    if info.get("private") is not True:
        raise LedgerError("El repositorio del historial debe ser PRIVADO")


def _read(file_url: str, token: str, branch: str) -> tuple[dict | None, str | None]:
    response = _api(file_url + "?ref=" + quote(branch, safe=""), token)
    if response is None:
        return None, None
    if response.get("type") != "file" or not isinstance(response.get("sha"), str):
        raise LedgerError("GitHub no devolvió un archivo del historial válido")
    try:
        decoded = base64.b64decode(response["content"], validate=False)
        if len(decoded) > MAX_BYTES:
            raise LedgerError("Historial supera el tamaño máximo")
        document = json.loads(decoded)
        return validate_ledger(document), response["sha"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        raise LedgerError("Historial privado dañado o no legible") from None


def _write(file_url: str, token: str, branch: str, ledger: dict,
           sha: str | None) -> None:
    document = json.dumps(validate_ledger(ledger), ensure_ascii=False, separators=(",", ":"))
    encoded = document.encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise LedgerError("Historial supera el tamaño máximo; exporta y archiva")
    payload = {
        "message": "Actualizar historial privado Sports Edge AI",
        "content": base64.b64encode(encoded).decode("ascii"),
        "branch": branch,
    }
    if sha is not None:
        payload["sha"] = sha
    result = _api(file_url, token, data=payload)
    if not result or not isinstance(result.get("content"), dict):
        raise LedgerError("GitHub no confirmó el guardado")


def read_ledger(repo: str, token: str, *, branch: str = "main",
                path: str = "private/historial.json") -> dict | None:
    repo_url, file_url = _paths(repo, branch, path)
    _check_private(repo_url, token)
    return _read(file_url, token, branch)[0]


def initialize(repo: str, token: str, amount: object, currency: str = "MXN",
               *, branch: str = "main", path: str = "private/historial.json") -> dict:
    repo_url, file_url = _paths(repo, branch, path)
    _check_private(repo_url, token)
    existing, _ = _read(file_url, token, branch)
    if existing is not None:
        return existing
    new = new_ledger(amount, currency)
    _write(file_url, token, branch, new, None)
    return new


def transact(repo: str, token: str, operation: Callable[[dict], T],
             *, branch: str = "main", path: str = "private/historial.json") -> T:
    repo_url, file_url = _paths(repo, branch, path)
    _check_private(repo_url, token)
    ledger, sha = _read(file_url, token, branch)
    if ledger is None:
        raise LedgerError("Primero configura el bank inicial")
    result = operation(ledger)
    _write(file_url, token, branch, ledger, sha)
    return result


def restore_backup(repo: str, token: str, contents: bytes,
                   *, branch: str = "main", path: str = "private/historial.json") -> dict:
    if len(contents) > MAX_BYTES:
        raise LedgerError("Archivo demasiado grande")
    try:
        ledger = validate_ledger(json.loads(contents))
    except (TypeError, ValueError, UnicodeDecodeError):
        raise LedgerError("Copia JSON inválida") from None
    repo_url, file_url = _paths(repo, branch, path)
    _check_private(repo_url, token)
    existing, _ = _read(file_url, token, branch)
    if existing is not None:
        raise LedgerError("Ya existe historial; no se sobreescribirá")
    _write(file_url, token, branch, ledger, None)
    return ledger
