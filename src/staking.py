"""Motor matemático de valor esperado y riesgo de Sports Edge AI.
No genera picks reales ni garantiza rentabilidad. Sin validación no propone apuestas.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from .math_utils import american_to_decimal

@dataclass(frozen=True)
class BetAssessment:
    odds_american: float
    model_probability: float
    implied_probability: float
    expected_roi: float
    conservative_probability: float | None
    conservative_expected_roi: float | None
    full_kelly_fraction: float | None
    suggested_bankroll_fraction: float
    status: str

    def to_dict(self) -> dict:
        return asdict(self)

def assess_bet(
    odds_american: float,
    model_probability: float,
    *,
    model_validated: bool = False,
    probability_lower_bound: float | None = None,
    min_conservative_edge: float = 0.01,
    kelly_multiplier: float = 0.25,
    max_bankroll_fraction: float = 0.01,
) -> BetAssessment:
    """Evaluate odds conservatively. Shares are fractions, not percentages.

    Returns zero stake unless a model independently validated and calibrated
    supplies an uncertainty bound above break-even + buffer. Caller must check
    price freshness, same-event correlation, total exposure, and legal context.
    """
    for name, value in {
        "odds_american": odds_american,
        "model_probability": model_probability,
        "min_conservative_edge": min_conservative_edge,
        "kelly_multiplier": kelly_multiplier,
        "max_bankroll_fraction": max_bankroll_fraction,
    }.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError(f"{name} debe ser un número finito")
    if abs(odds_american) < 100:
        raise ValueError("La cuota americana debe ser <= -100 o >= +100")
    if not (0 <= model_probability <= 1):
        raise ValueError("La probabilidad debe estar entre cero y uno")
    if not 0 <= min_conservative_edge <= 1 or not 0 <= kelly_multiplier <= 1 or not 0 <= max_bankroll_fraction <= 0.05:
        raise ValueError("Límites de riesgo no válidos")
    if probability_lower_bound is not None:
        if isinstance(probability_lower_bound, bool) or not isinstance(probability_lower_bound, (int,float)) or not isfinite(probability_lower_bound):
            raise ValueError("La probabilidad conservadora debe ser numérica")
        if not 0 <= probability_lower_bound <= model_probability:
            raise ValueError("La probabilidad conservadora debe estar entre 0 y la probabilidad estimada")

    dec = american_to_decimal(odds_american)
    implied = 1.0 / dec
    expected_roi = model_probability * dec - 1.0
    lower_ev = probability_lower_bound * dec - 1.0 if probability_lower_bound is not None else None
    status = "MODELO_SIN_VALIDAR"
    kelly = None
    fraction = 0.0
    if model_validated and probability_lower_bound is None:
        status = "FALTA_INTERVALO_DE_INCERTIDUMBRE"
    elif model_validated:
        b = dec - 1
        kelly = max(0.0, (probability_lower_bound * b - (1-probability_lower_bound)) / b)
        if probability_lower_bound <= implied + min_conservative_edge:
            status = "SIN_VENTAJA_CONSERVADORA"
        else:
            status = "CANDIDATO_PARA_REVISION"
            fraction = min(max_bankroll_fraction, kelly * kelly_multiplier)
    return BetAssessment(
        odds_american=float(odds_american),
        model_probability=float(model_probability),
        implied_probability=implied,
        expected_roi=expected_roi,
        conservative_probability=probability_lower_bound,
        conservative_expected_roi=lower_ev,
        full_kelly_fraction=kelly,
        suggested_bankroll_fraction=fraction,
        status=status,
    )
