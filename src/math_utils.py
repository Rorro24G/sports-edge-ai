"""Aritmética de momios y verificación conservadora de parlays."""
from dataclasses import dataclass
from math import prod


def american_to_decimal(american: float) -> float:
    if american == 0:
        raise ValueError("Las cuotas americanas no pueden ser cero")
    return 1 + american / 100 if american > 0 else 1 + 100 / abs(american)


def implied_probability(american: float) -> float:
    return 1 / american_to_decimal(american)


def expected_roi(decimal_odds: float, probability: float) -> float:
    if decimal_odds <= 1:
        raise ValueError("La cuota decimal debe ser mayor que 1")
    if not 0 <= probability <= 1:
        raise ValueError("La probabilidad debe estar entre 0 y 1")
    return probability * decimal_odds - 1


def no_vig_probabilities(american_by_outcome: dict[str, float]) -> dict[str, float]:
    """Normalización proporcional de probabilidades implícitas; no es un modelo propio."""
    if len(american_by_outcome) < 2:
        raise ValueError("Se requieren al menos dos resultados")
    raw = {name: implied_probability(odd) for name, odd in american_by_outcome.items()}
    total = sum(raw.values())
    if total <= 0:
        raise ValueError("Cuotas inválidas")
    return {name: p / total for name, p in raw.items()}


@dataclass(frozen=True)
class ParlayLeg:
    event_id: str
    decimal_odds: float
    estimated_probability: float


def independent_parlay(legs: list[ParlayLeg], *, independence_validated: bool = False) -> dict[str, float]:
    """Solo calcula con independencia previamente evaluada; NUNCA la supone."""
    if not independence_validated:
        raise ValueError("Correlaciones no evaluadas: cálculo de parlay bloqueado")
    if len(legs) < 2:
        raise ValueError("Un parlay requiere dos o más selecciones")
    if len({leg.event_id for leg in legs}) != len(legs):
        raise ValueError("Parlay del mismo evento: requiere modelo conjunto específico")
    for leg in legs:
        if not 0 <= leg.estimated_probability <= 1 or leg.decimal_odds <= 1:
            raise ValueError("Probabilidad o cuota inválida")
    p = prod(leg.estimated_probability for leg in legs)
    d = prod(leg.decimal_odds for leg in legs)
    return {"joint_probability": p, "decimal_odds": d, "expected_roi": expected_roi(d, p)}
