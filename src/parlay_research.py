"""Borradores de combinadas derivados de referencias públicas de Covers.

NO son recomendaciones de valor, ni momios ofrecidos por una única casa.
Las cuotas se multiplican solamente como cálculo matemático hipotético.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from .market_summary import implied_percent
from .pick_reference import covers_projection

LOCAL = ZoneInfo("America/Mexico_City")
LEAGUES = ("NBA", "NHL", "NFL")
CENT = Decimal("0.01")


def _decimal_price(american: object) -> Decimal | None:
    if implied_percent(american) is None:
        return None
    quote = Decimal(str(american))
    return Decimal(1) + (
        quote / Decimal(100) if quote > 0 else Decimal(100) / abs(quote)
    )


def candidate_legs(report: dict, *, now: datetime | None = None) -> dict[str, list[dict]]:
    """Use only future games with Covers ML, exact date, ESPN-matched identity."""
    clock = now or datetime.now(LOCAL)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=LOCAL)
    today = clock.astimezone(LOCAL).date().isoformat()
    if not isinstance(report, dict) or report.get("date_cdmx") != today:
        return {league: [] for league in LEAGUES}
    sections = report.get("leagues")
    if not isinstance(sections, dict):
        return {league: [] for league in LEAGUES}
    result = {league: [] for league in LEAGUES}
    for league in LEAGUES:
        section = sections.get(league, {})
        events = section.get("events", []) if isinstance(section, dict) else []
        seen = set()
        for event in events[:150]:
            if not isinstance(event, dict) or event.get("fecha_cdmx") != today:
                continue
            if not event.get("fuente_covers"):
                continue
            # Both teams verified in ESPN for this exact match.
            espn = event.get("espn")
            if not isinstance(espn, dict) or not espn.get("evento"):
                continue
            scores = event.get("proyeccion_covers")
            quotes = event.get("momios_covers")
            if not isinstance(scores, list) or len(scores) != 2:
                continue
            if not isinstance(quotes, list) or len(quotes) != 2:
                continue
            game = {
                "liga": league, "partido": event.get("partido"),
                "fecha_cdmx": today, "hora_cdmx": event.get("hora_cdmx"),
                "proyeccion_visitante": scores[0], "proyeccion_local": scores[1],
                "momio_visitante": quotes[0], "momio_local": quotes[1],
                "fuente": event["fuente_covers"],
            }
            reference = covers_projection(game, now=clock)
            if not reference or not reference["vigente_para_analisis_prepartido"]:
                continue
            price = reference["momio_covers"]
            if price is None:
                continue
            event_key = (league, reference["partido"], today)
            if event_key in seen:
                continue
            seen.add(event_key)
            result[league].append({
                "liga": league,
                "evento": reference["partido"],
                "dia": today,
                "hora_cdmx": reference["hora_cdmx"],
                "seleccion": reference["seleccion_de_referencia"],
                "momio_covers": price,
                "margen_marcador": reference["margen_proyectado"],
                "fuente": reference["fuente"],
                "espn_evento": str(espn["evento"]),
                "decimal_teorica": _decimal_price(price),
            })
        result[league].sort(key=lambda row: (-row["margen_marcador"],
                                            row["hora_cdmx"], row["evento"]))
    return result


def build_reference_parlays(report: dict, *, count: int = 3, legs_per_parlay: int = 3,
                            more_than_ten: bool = False,
                            now: datetime | None = None) -> list[dict]:
    """At most 2-3 candidate combinations; never pad with invented games.

    Default maximum 10 legs. Over 10 allowed only with explicit opt-in.
    Same event is never included twice in a combination.
    """
    if isinstance(count, bool) or count not in (2, 3):
        raise ValueError("Se admiten dos o tres alternativas por consulta")
    if isinstance(legs_per_parlay, bool) or not isinstance(legs_per_parlay, int):
        raise ValueError("Número de selecciones incorrecto")
    if legs_per_parlay < 1 or legs_per_parlay > (30 if more_than_ten else 10):
        raise ValueError("Máximo 10 selecciones, salvo autorización para más")
    groups = candidate_legs(report, now=now)
    available = sum(len(group) for group in groups.values())
    if not available:
        return []
    # Different offsets create genuinely alternative combinations.
    proposals = []
    seen = set()
    for index in range(count):
        chosen = []
        candidates = []
        # Rotate within each league and interleave, not compare NBA point margins
        # directly with NHL goals; these scales are not interchangeable.
        max_count = max((len(groups[league]) for league in LEAGUES), default=0)
        for shift in range(max_count):
            for league in LEAGUES:
                group = groups[league]
                if shift < len(group):
                    candidates.append(group[(shift + index) % len(group)])
        for row in candidates:
            if row not in chosen and len(chosen) < legs_per_parlay:
                chosen.append(row)
        if len(chosen) < 2 and legs_per_parlay >= 2:
            continue
        if not chosen:
            continue
        signature = frozenset((row["liga"], row["evento"]) for row in chosen)
        if signature in seen:
            continue
        seen.add(signature)
        theoretical = Decimal(1)
        for row in chosen:
            theoretical *= row["decimal_teorica"]
        proposals.append({
            "nombre": f"Alternativa {len(proposals) + 1}",
            "selecciones": chosen,
            "num_selecciones": len(chosen),
            "tipo": "APUESTA_SIMPLE_DE_REFERENCIA" if len(chosen) == 1 else
                    "BORRADOR_PARLAY_NO_VALIDADO",
            "cuota_decimal_teorica": str(theoretical.quantize(CENT, rounding=ROUND_HALF_UP)),
            "probabilidad_conjunta": None,
            "ev_propio": None,
            "stake_recomendado": None,
            "cuota_real_ofrecida_por_casa": None,
            "restricciones": (
                "Precios de Covers potencialmente de distintas casas y momentos; "
                "no constituye una cuota combinada disponible. No se evaluaron "
                "correlaciones ni probabilidades predictivas."
            ),
        })
    return proposals


def parlay_review_prompt(proposal: dict) -> str:
    """Self-contained discussion prompt, with sources, not a betting instruction."""
    lines = [
        "Analicemos riesgos y posibles errores de este borrador; NO son picks "
        "propios validados ni un cupón disponible en una casa de apuestas.",
    ]
    for row in proposal["selecciones"]:
        lines.append(
            f"- {row['liga']}: {row['evento']}, {row['hora_cdmx']} CDMX, "
            f"{row['seleccion']} a momio {row['momio_covers']} publicado por Covers. "
            f"Fuente: {row['fuente']}"
        )
    lines.append(
        f"Producto teórico de momios decimales: "
        f"{proposal['cuota_decimal_teorica']} (NO es una cuota real ofrecida)."
    )
    lines.append("¿Qué datos faltan para decidir, cuáles son los riesgos y "
                 "por qué convendría excluir alguna selección? "
                 "No inventes probabilidades ni ganancias.")
    return "\n".join(lines)
