"""Registro privado de apuestas aceptadas por el usuario.

No crea picks, no apuesta ni asume que una cuota tiene valor. Separa resultado
realizado de apuestas pendientes y no cuenta pushes/void como aciertos.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4

VALID_SPORTS = ("NBA", "NFL", "NHL", "ATP", "WTA", "OTRO")
VALID_STATUSES = ("pendiente", "ganado", "perdido", "push", "anulado")
CENT = Decimal("0.01")
PERCENT = Decimal("0.01")
MAX_BETS = 3000


class LedgerError(ValueError):
    pass


def money(value) -> Decimal:
    if isinstance(value, bool):
        raise LedgerError("Cantidad no válida")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise LedgerError("Cantidad no válida") from None
    if not result.is_finite():
        raise LedgerError("La cantidad debe ser finita")
    return result.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_american(value) -> int:
    if isinstance(value, bool):
        raise LedgerError("Momio no válido")
    try:
        text = str(value).strip()
        integer = int(text)
        if not text.lstrip("+-").isdigit() or abs(integer) < 100 or abs(integer) > 100000:
            raise LedgerError("Momio americano inválido: usa +150 o -110")
        return integer
    except (TypeError, ValueError):
        raise LedgerError("Momio americano inválido: usa +150 o -110") from None


def new_ledger(initial_bank: object, currency: str = "MXN") -> dict:
    bank = money(initial_bank)
    if bank <= 0:
        raise LedgerError("El bank inicial debe ser mayor que cero")
    if currency not in ("MXN", "USD"):
        raise LedgerError("Moneda admitida: MXN o USD")
    return {"version": 1, "currency": currency, "initial_bank": str(bank),
            "bets": []}


def _profit(bet: dict) -> Decimal:
    status = bet["status"]
    stake = money(bet["stake"])
    if status == "perdido":
        return -stake
    if status == "ganado":
        price = parse_american(bet["odds_american"])
        return (stake * (Decimal(price) / 100 if price > 0
                         else Decimal(100) / abs(Decimal(price)))).quantize(
                             CENT, rounding=ROUND_HALF_UP)
    return Decimal("0.00")


def metrics(ledger: dict) -> dict:
    initial = money(ledger["initial_bank"])
    bets = ledger["bets"]
    pnl = sum((_profit(b) for b in bets if b["status"] != "pendiente"), Decimal("0"))
    pending = sum((money(b["stake"]) for b in bets if b["status"] == "pendiente"), Decimal("0"))
    settled = [b for b in bets if b["status"] in ("ganado", "perdido")]
    invested = sum((money(b["stake"]) for b in settled), Decimal("0"))
    wins = sum(b["status"] == "ganado" for b in settled)
    losses = sum(b["status"] == "perdido" for b in settled)
    balance = initial + pnl
    free = balance - pending
    return {
        "bank_initial": initial, "bank_current": balance,
        "bank_available": free, "pending_stakes": pending, "net_profit": pnl,
        "pnl_pct_initial": ((pnl / initial) * 100).quantize(PERCENT) if initial else None,
        "roi": ((pnl / invested) * 100).quantize(PERCENT) if invested else None,
        "wins": wins, "losses": losses, "pending": sum(b["status"] == "pendiente" for b in bets),
        "pushes": sum(b["status"] == "push" for b in bets),
        "voids": sum(b["status"] == "anulado" for b in bets),
        "hit_rate": (Decimal(wins) / Decimal(wins + losses) * 100).quantize(
            PERCENT) if wins + losses else None,
        "suggested_stake_5pct": max(Decimal("0"), free * Decimal("0.05")).quantize(
            CENT, rounding=ROUND_HALF_UP),
    }


def add_bet(ledger: dict, *, sport: str, event: str, selection: str,
            odds_american: object, stake: object, date_cdmx: str | None = None,
            notes: str = "", bet_id: str | None = None) -> dict:
    if sport.upper().strip() not in VALID_SPORTS:
        raise LedgerError("Liga no admitida")
    if not event.strip() or len(event.strip()) > 180:
        raise LedgerError("Indica el enfrentamiento")
    if not selection.strip() or len(selection.strip()) > 160:
        raise LedgerError("Indica el pick elegido")
    from datetime import date as date_type
    if date_cdmx:
        try:
            date_type.fromisoformat(date_cdmx)
        except ValueError:
            raise LedgerError("Fecha no válida: YYYY-MM-DD") from None
    price = parse_american(odds_american)
    amount = money(stake)
    if amount <= 0:
        raise LedgerError("El monto debe ser positivo")
    available = metrics(ledger)["bank_available"]
    if amount > available:
        raise LedgerError("El monto excede el bank disponible")
    if len(ledger["bets"]) >= MAX_BETS:
        raise LedgerError("Registro lleno; exporta y archiva antes de continuar")
    if bet_id and any(b["id"] == bet_id for b in ledger["bets"]):
        raise LedgerError("Ya existe un registro con ese identificador")
    balance = metrics(ledger)["bank_current"]
    bet = {
        "id": bet_id or uuid4().hex,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_date_cdmx": date_cdmx,
        "sport": sport.upper().strip(), "event": event.strip(),
        "selection": selection.strip(), "odds_american": price,
        "stake": str(amount),
        "bank_at_entry": str(balance),
        "bank_percent_at_entry": str((amount / balance * 100).quantize(PERCENT))
            if balance > 0 else "0.00",
        "status": "pendiente", "settled_at_utc": None,
        "notes": notes.strip()[:500], "entered_by": "usuario",
    }
    ledger["bets"].append(bet)
    return bet


def settle_bet(ledger: dict, bet_id: str, status: str) -> dict:
    if status not in VALID_STATUSES or status == "pendiente":
        raise LedgerError("Resultado permitido: ganado, perdido, push o anulado")
    for bet in ledger["bets"]:
        if bet["id"] == bet_id:
            if bet["status"] != "pendiente":
                raise LedgerError("Ya liquidado; no se cambiará el historial sin corrección auditada")
            bet["status"] = status
            bet["settled_at_utc"] = datetime.now(timezone.utc).isoformat()
            return bet
    raise LedgerError("No existe esa apuesta")


def ledger_rows(ledger: dict) -> list[dict]:
    return [{
        "ID": b["id"], "Fecha": b.get("event_date_cdmx") or "",
        "Liga": b["sport"], "Partido": b["event"],
        "Pick": b["selection"], "Momio": b["odds_american"],
        "Apostado": str(money(b["stake"])),
        "% bank al registrar": b["bank_percent_at_entry"],
        "Resultado": b["status"], "Ganancia / pérdida": str(_profit(b))
        if b["status"] != "pendiente" else "",
        "Notas": b.get("notes", ""),
    } for b in ledger["bets"]]
