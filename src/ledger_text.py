"""Interpreta instrucciones explícitas de registrar una apuesta, sin adivinar dinero.

No registra órdenes ambiguas: exige liga, partido, selección, momio y monto.
El usuario confirma el borrador antes de guardarlo.
"""
from __future__ import annotations
import re
from .pick_ledger import LedgerError, parse_american, money

TRIGGER = re.compile(
    r"\b(?:voy a (?:meter|apostar)|registra(?:r)?|anota(?:r)?|apost[eé]|met[ií])\b",
    re.I,
)
SPORT = re.compile(r"\b(NBA|NFL|NHL|ATP|WTA)\b", re.I)
ODDS = re.compile(r"(?<![\w.])([+-]\d{3,5})(?!\w)")
STAKES = re.compile(
    r"(?:\b(?:apuesto|monto|stake|por|con)\s*(?:de\s*)?|\$\s*)"
    r"(\d+(?:[.,]\d{1,2})?)\s*(?:mxn|pesos|usd|d[oó]lares)?\b",
    re.I,
)
DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")

def parse_bet_message(text: str) -> dict:
    if not TRIGGER.search(text):
        raise LedgerError("Empieza con 'voy a meter' o 'registra'")
    sport_match = SPORT.search(text)
    if not sport_match:
        raise LedgerError("Falta liga (NBA, NFL, NHL, ATP o WTA)")
    odds_match = ODDS.search(text)
    if not odds_match:
        raise LedgerError("Falta momio americano, por ejemplo -110 o +150")
    odds = parse_american(odds_match.group(1))
    stakes = list(STAKES.finditer(text))
    if len(stakes) != 1:
        raise LedgerError("Indica un solo monto, por ejemplo 'con $100'")
    amount = money(stakes[0].group(1).replace(",", "."))
    if amount <= 0:
        raise LedgerError("El monto debe ser positivo")
    # Evitamos leer cifras de totales/handicaps como stake.
    game_match = re.search(
        r"\bpartido\s*[:=]?\s*(.+?)\s*[,;]\s*"
        r"(?:pick|selecci[oó]n)\s*[:=]?\s*(.+?)"
        r"(?=\s*[,;]\s*(?:momio|cuota)|$)",
        text, re.I,
    )
    if not game_match:
        raise LedgerError(
            "Formato: voy a meter NBA, partido: Lakers vs Warriors; "
            "pick: Lakers ML; momio: -110; con $100"
        )
    event = game_match.group(1).strip(" ;,")
    pick = game_match.group(2).strip(" ;,")
    pick = re.split(r"\s*[,;]\s*(?:momio|cuota)\b", pick, maxsplit=1, flags=re.I)[0].strip()
    if not event or not pick:
        raise LedgerError("Falta el partido o la selección")
    dates = DATE.findall(text)
    return {"sport": sport_match.group(1).upper(), "event": event,
            "selection": pick, "odds_american": odds, "stake": str(amount),
            "date_cdmx": dates[0] if len(dates) == 1 else None}
