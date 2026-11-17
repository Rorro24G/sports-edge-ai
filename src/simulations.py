"""Motor Monte Carlo de laboratorio para totales NFL y NBA.

Las medias, desviaciones y correlacion DEBEN venir de un modelo ajustado con
datos historicos anteriores al partido. Una entrada manual no constituye un pick.
Ningun resultado es una probabilidad validada sin backtesting.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite, sqrt
from random import Random


@dataclass(frozen=True)
class GameScenario:
    sport: str
    away_mean: float
    home_mean: float
    away_sd: float
    home_sd: float
    score_correlation: float
    total_line: float
    simulations: int = 10_000
    seed: int = 42

    def validate(self) -> None:
        if self.sport not in ("NFL", "NBA"):
            raise ValueError("Por ahora el simulador admite NFL o NBA")
        for key in ("away_mean", "home_mean", "away_sd", "home_sd", "score_correlation", "total_line"):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ValueError(f"{key} debe ser numerico y finito")
        if self.away_mean < 0 or self.home_mean < 0 or self.total_line < 0:
            raise ValueError("Medias y linea de puntos no pueden ser negativas")
        if self.away_sd <= 0 or self.home_sd <= 0:
            raise ValueError("Las desviaciones deben ser positivas")
        if abs(self.score_correlation) >= 1:
            raise ValueError("La correlacion debe estar estrictamente entre -1 y 1")
        if isinstance(self.simulations, bool) or not isinstance(self.simulations, int) or not 1000 <= self.simulations <= 100000:
            raise ValueError("simulations debe ser un entero entre 1000 y 100000")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise ValueError("seed debe ser un entero")


@dataclass(frozen=True)
class SimulationResult:
    sport: str
    simulations: int
    line: float
    over_count: int
    under_count: int
    push_count: int
    over_probability: float
    under_probability: float
    push_probability: float
    home_win_probability: float
    simulated_mean_total: float
    over_mc_margin_95: float
    simulated_p10_total: int
    simulated_median_total: int
    simulated_p90_total: int
    histogram: list[dict]
    status: str = "ESCENARIO_NO_VALIDADO"
    model_note: str = "Distribucion normal bivariada y puntos redondeados; sin datos ni backtesting certificados"

    def to_dict(self) -> dict:
        return asdict(self)


def simulate_totals(scenario: GameScenario) -> SimulationResult:
    """Simula marcadores conjuntos y evalua over/under con posibilidad de push.

    El margen al 95% mide SOLO ruido Monte Carlo, NO el error de prediccion
    ni incertidumbre en los parametros del modelo.
    """
    scenario.validate()
    rng = Random(scenario.seed)
    over = under = push = home_wins = total_sum = 0
    totals = []
    correlated_scale = sqrt(1.0 - scenario.score_correlation ** 2)
    for _ in range(scenario.simulations):
        z1 = rng.gauss(0, 1)
        z2 = scenario.score_correlation * z1 + correlated_scale * rng.gauss(0, 1)
        away = max(0, round(scenario.away_mean + scenario.away_sd * z1))
        home = max(0, round(scenario.home_mean + scenario.home_sd * z2))
        total = away + home
        totals.append(total)
        total_sum += total
        if total > scenario.total_line:
            over += 1
        elif total < scenario.total_line:
            under += 1
        else:
            push += 1
        if home > away:
            home_wins += 1
    n = scenario.simulations
    p_over = over / n
    totals.sort()
    width = 5 if scenario.sport == "NFL" else 10
    bins = {}
    for total in totals:
        center = (total // width) * width
        bins[center] = bins.get(center, 0) + 1
    histogram = [
        {"Puntos": str(left) + "–" + str(left + width - 1),
         "Frecuencia": bins[left]}
        for left in sorted(bins)
    ]
    return SimulationResult(
        sport=scenario.sport,
        simulations=n,
        line=scenario.total_line,
        over_count=over,
        under_count=under,
        push_count=push,
        over_probability=p_over,
        under_probability=under / n,
        push_probability=push / n,
        home_win_probability=home_wins / n,
        simulated_mean_total=total_sum / n,
        over_mc_margin_95=1.96 * sqrt(p_over * (1 - p_over) / n),
        simulated_p10_total=totals[int((n - 1) * 0.10)],
        simulated_median_total=totals[int((n - 1) * 0.50)],
        simulated_p90_total=totals[int((n - 1) * 0.90)],
        histogram=histogram,
    )
