"""SQLite local y exportación JSON del libro personal.

Advertencia: Streamlit Community Cloud no ofrece disco duradero. Para conservar
el registro tras reinicios se necesita volumen persistente/DB remota; se
proporciona exportación manual mientras tanto. Nunca se guarda en el repo.
"""
from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
from typing import Callable, TypeVar

from .pick_ledger import LedgerError, new_ledger, MAX_BETS, money, parse_american, VALID_STATUSES

T = TypeVar("T")
MAX_BYTES = 2_000_000

def _connect(path: str) -> sqlite3.Connection:
    parent = Path(path).expanduser().resolve().parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    connection = sqlite3.connect(str(Path(path).expanduser()), timeout=8, isolation_level=None)
    connection.execute("PRAGMA busy_timeout = 8000")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS private_ledger (id INTEGER PRIMARY KEY CHECK(id = 1), data TEXT NOT NULL)"
    )
    return connection


def validate_ledger(data: dict) -> dict:
    if not isinstance(data, dict) or data.get("version") != 1:
        raise LedgerError("Archivo de historial no admitido")
    if data.get("currency") not in ("MXN", "USD"):
        raise LedgerError("Moneda de historial incorrecta")
    if money(data.get("initial_bank")) <= 0:
        raise LedgerError("Bank inicial incorrecto")
    bets = data.get("bets")
    if not isinstance(bets, list) or len(bets) > MAX_BETS:
        raise LedgerError("Registros inválidos o demasiados")
    seen = set()
    for b in bets:
        if not isinstance(b, dict) or not isinstance(b.get("id"), str) or b["id"] in seen:
            raise LedgerError("ID duplicado o incorrecto")
        seen.add(b["id"])
        if b.get("status") not in VALID_STATUSES:
            raise LedgerError("Estado incorrecto")
        if money(b.get("stake")) <= 0:
            raise LedgerError("Stake incorrecto")
        parse_american(b.get("odds_american"))
        if not isinstance(b.get("sport"), str) or not isinstance(b.get("event"), str):
            raise LedgerError("Partido incorrecto")
    return data


def read_ledger(path: str) -> dict | None:
    with _connect(path) as conn:
        row = conn.execute("SELECT data FROM private_ledger WHERE id = 1").fetchone()
        return validate_ledger(json.loads(row[0])) if row else None


def transact(path: str, operation: Callable[[dict], T]) -> T:
    """Atomic transaction: rejected commands never partially change DB."""
    conn = _connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT data FROM private_ledger WHERE id = 1").fetchone()
        if row is None:
            raise LedgerError("Primero configura el bank inicial")
        ledger = validate_ledger(json.loads(row[0]))
        result = operation(ledger)
        payload = json.dumps(ledger, ensure_ascii=False, separators=(",", ":"))
        if len(payload.encode("utf-8")) > MAX_BYTES:
            raise LedgerError("Archivo demasiado grande; exporta antes")
        conn.execute("UPDATE private_ledger SET data = ? WHERE id = 1", (payload,))
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize(path: str, amount: object, currency: str = "MXN") -> dict:
    new = new_ledger(amount, currency)
    payload = json.dumps(new, ensure_ascii=False)
    with _connect(path) as conn:
        conn.execute("INSERT OR IGNORE INTO private_ledger(id, data) VALUES (1, ?)", (payload,))
        row = conn.execute("SELECT data FROM private_ledger WHERE id = 1").fetchone()
        return validate_ledger(json.loads(row[0]))


def export_json(ledger: dict) -> bytes:
    validate_ledger(ledger)
    return json.dumps(ledger, ensure_ascii=False, indent=2).encode("utf-8")


def restore_backup(path: str, contents: bytes) -> dict:
    if len(contents) > MAX_BYTES:
        raise LedgerError("Copia demasiado grande")
    try:
        ledger = validate_ledger(json.loads(contents))
    except (ValueError, UnicodeDecodeError, TypeError):
        raise LedgerError("Copia JSON inválida") from None
    payload = json.dumps(ledger, ensure_ascii=False)
    conn = _connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM private_ledger WHERE id = 1").fetchone():
            raise LedgerError("Ya existe historial; no se sobreescribirá sin una migración controlada")
        conn.execute("INSERT INTO private_ledger(id, data) VALUES (1, ?)", (payload,))
        conn.commit()
        return ledger
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
