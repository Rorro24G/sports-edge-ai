"""Independent ESPN-driven parlay RESEARCH drafts; no Covers pick copying.

Selection happens upstream in independent_picks.build_slate. Covers may supply
a quoted moneyline only AFTER the model picked its own side. Neither prices
nor Covers projections can change the proposed leg or its ranking.

No combined win probability, expected value, ROI, stake, or sportsbook ticket
is implied by these drafts. If there are not two independent future picks,
there cannot be an autonomous parlay.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .independent_picks import VERSION
from .parlay_research import _decimal_price

LOCAL = ZoneInfo("America/Mexico_City")
SPORTS = ("NBA", "NFL", "NHL")
QUANT = Decimal("0.01")


def _verified_url(value: object, domain: str) -> str | None:
    if not isinstance(value, str):
        return None
    p = urlsplit(value)
    if (p.scheme == "https" and p.username is None and p.password is None
            and (p.hostname == domain or (p.hostname or "").endswith("." + domain))):
        return value
    return None


def _future(item: dict, day: date, now: datetime) -> bool:
    if item.get("status") != "CANDIDATO_EXPERIMENTAL":
        return False
    if item.get("sport") not in SPORTS or not str(item.get("event_id") or "").isdigit():
        return False
    time = item.get("time")
    if not isinstance(time, str):
        return False
    try:
        kick = datetime.strptime(time, "%H:%M").time()
        game_time = datetime.combine(day, kick, tzinfo=LOCAL)
    except (ValueError, TypeError):
        return False
    return game_time > now


def _ordered_candidates(slate: dict, day: date, now: datetime) -> list[dict]:
    """Round-robin leagues; never rank uncalibrated NBA vs NHL percentages."""
    groups: dict[str, list[dict]] = {sport: [] for sport in SPORTS}
    seen = set()
    for item in slate.get("picks") or []:
        if not isinstance(item, dict) or not _future(item, day, now):
            continue
        if item.get("version") != VERSION or item.get("model_validated") is not False:
            continue
        event_key = (item["sport"], str(item["event_id"]))
        if event_key in seen:
            continue
        selected = item.get("team")
        side = item.get("side")
        if (not isinstance(selected, str) or not selected.strip()
                or side not in ("local", "visitante")
                or selected != item.get("home" if side == "local" else "away")):
            continue
        # Require an actual ESPN trace; never invent a fixture or source.
        espn = _verified_url(item.get("espn_url"), "espn.com")
        if espn is None:
            continue
        seen.add(event_key)
        raw_price = item.get("market_price")
        covers = _verified_url(item.get("market_source"), "covers.com")
        price = str(raw_price) if covers and _decimal_price(raw_price) is not None else None
        groups[item["sport"]].append({
            "liga": item["sport"],
            "evento": item["away"] + " @ " + item["home"],
            "espn_evento": str(item["event_id"]),
            "dia": day.isoformat(),
            "hora_cdmx": item["time"],
            "seleccion": selected,
            "lado": side,
            "modelo": item["version"],
            "fuente": espn,
            "momio_covers": price,
            "fuente_covers": covers if price else None,
            "decimal_teorica": _decimal_price(price) if price else None,
            "robustez": item.get("stability"),
            "probabilidad_experimental": item.get("probability_experimental"),
            "motivo": str(item.get("reason") or ""),
        })
    for sport in SPORTS:
        groups[sport].sort(
            key=lambda x: (
                -float(x["robustez"] or 0),
                x["hora_cdmx"],
                x["espn_evento"],
            )
        )
    max_count = max((len(v) for v in groups.values()), default=0)
    return [
        groups[sport][i] for i in range(max_count) for sport in SPORTS
        if i < len(groups[sport])
    ]


def build_own_parlays(slate: dict, day: date, *, count: int = 3,
                      legs_per_parlay: int = 2, more_than_ten: bool = False,
                      now: datetime | None = None) -> dict:
    """Build distinct, real-fixture parlay drafts without forcing weak picks."""
    if not isinstance(slate, dict) or not isinstance(day, date):
        raise ValueError("Datos o fecha inválidos para el parlay")
    if type(count) is not int or count not in (2, 3):
        raise ValueError("Puedes comparar 2 o 3 alternativas")
    if (type(legs_per_parlay) is not int or
            not 2 <= legs_per_parlay <= (30 if more_than_ten else 10)):
        raise ValueError("Cada parlay requiere 2 a 10 selecciones, salvo autorización")
    if slate.get("model") != VERSION:
        raise ValueError("Modelo de Picks incompatible con el constructor")
    clock = now or datetime.now(LOCAL)
    clock = clock.replace(tzinfo=LOCAL) if clock.tzinfo is None else clock.astimezone(LOCAL)
    if day != clock.date():
        # No selecting events from yesterday, nor future dates without a dedicated evaluation.
        return {"proposals": [], "available": 0, "eligible_games": 0,
                "evaluated": 0, "excluded": {},
                "reason": "El constructor automático trabaja con los próximos partidos de hoy."}
    pool = _ordered_candidates(slate, day, clock)
    available = len(pool)
    reviewed = slate.get("evaluated") or []
    excluded = Counter(
        str(row.get("status", "SIN_DATOS"))
        for row in reviewed if isinstance(row, dict)
        and row.get("status") != "CANDIDATO_EXPERIMENTAL"
    )
    proposals = []
    used_signatures = set()
    length = min(legs_per_parlay, available)
    if length >= 2:
        for rotation in range(available):
            # Shift through the real ESPN picks so alternatives are not copies
            # and no game repeats inside the same combination.
            selected = [pool[(rotation + offset) % available] for offset in range(length)]
            signature = frozenset((row["liga"], row["espn_evento"]) for row in selected)
            if signature in used_signatures:
                continue
            used_signatures.add(signature)
            quoted = all(row["decimal_teorica"] is not None for row in selected)
            price = None
            if quoted:
                value = Decimal(1)
                for row in selected:
                    value *= row["decimal_teorica"]
                price = str(value.quantize(QUANT, rounding=ROUND_HALF_UP))
            proposals.append({
                "nombre": "Parlay propio " + str(len(proposals) + 1),
                "selecciones": selected,
                "num_selecciones": len(selected),
                "solicitadas": legs_per_parlay,
                "incompleto": len(selected) < legs_per_parlay,
                "tipo": "BORRADOR_SEAI_EXPERIMENTAL",
                "origen_decision": "ESPN + modelo Sports Edge AI",
                "cuota_decimal_teorica": price,
                "probabilidad_conjunta": None,
                "ev_propio": None,
                "stake_recomendado": None,
                "cuota_real_ofrecida_por_casa": None,
                "restricciones": (
                    "Los momios Covers son opcionales y pueden cambiar. No se "
                    "estimó dependencia entre selecciones. Sin modelo de "
                    "probabilidad conjunta calibrado ni rentabilidad validada."
                ),
            })
            if len(proposals) == count:
                break
    reason = ""
    if available < 2:
        reason = (
            "El cerebro encontró " + str(available) +
            " selección propia con historial suficiente. Un parlay necesita "
            "al menos 2 partidos distintos; no se usarán favoritos de Covers "
            "para rellenarlo."
        )
    elif len(proposals) < count:
        reason = (
            "Solo existen " + str(len(proposals)) +
            " combinaciones distintas con los partidos verificados disponibles."
        )
    return {
        "proposals": proposals,
        "available": available,
        "eligible_games": slate.get("eligible_games", 0),
        "evaluated": len(reviewed),
        "excluded": dict(excluded),
        "reason": reason,
        "model": VERSION,
        "date": day.isoformat(),
    }


def own_parlay_review_prompt(proposal: dict) -> str:
    """Review actual SEAI choices with ESPN sources and optional Covers quotes."""
    lines = [
        "Revisa CRÍTICAMENTE este borrador de parlay del cerebro Sports Edge AI. "
        "Las elecciones son propias del modelo ESPN, no Picks de Covers. "
        "No es una recomendación validada ni una apuesta ejecutada.",
    ]
    for item in proposal["selecciones"]:
        quote = (
            f"Momio de referencia Covers {item['momio_covers']}; "
            f"Fuente Covers: {item['fuente_covers']}"
            if item["momio_covers"] else "Momio externo NO verificado."
        )
        lines.append(
            "- " + item["liga"] + ": " + item["evento"] + " / " +
            item["hora_cdmx"] + " CDMX; elección propia: " +
            item["seleccion"] + " ML. Fuente: " + item["fuente"] + ". " + quote
        )
    if proposal["cuota_decimal_teorica"] is None:
        lines.append("No se calculó cuota combinada porque faltan momios verificables.")
    else:
        lines.append(
            "Producto hipotético de momios: " +
            proposal["cuota_decimal_teorica"] +
            " (NO es una cuota real ofrecida por una casa)."
        )
    lines.append(
        "¿Hay datos incompletos, partidos correlacionados, lesiones o razones "
        "para descartar alguna pierna? No inventes probabilidades conjuntas, "
        "EV, stake, rentabilidad ni fuentes."
    )
    return "\n".join(lines)
