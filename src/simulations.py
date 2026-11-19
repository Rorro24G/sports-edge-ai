"""Motor Monte Carlo de laboratorio para totales NFL y NBA.

Las medias, desviaciones y correlacion DEBEN venir de un modelo ajustado con
datos historicos anteriores al partido. Una entrada manual no constituye un pick.
Ningun resultado es una probabilidad validada sin backtesting.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite, sqrt
from statistics import stdev
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
    # Optional verified ESPN scores, most recent first: bootstrap mode.
    away_scored: tuple[float, ...] = ()
    away_allowed: tuple[float, ...] = ()
    home_scored: tuple[float, ...] = ()
    home_allowed: tuple[float, ...] = ()

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
        sequences = (self.away_scored, self.away_allowed,
                     self.home_scored, self.home_allowed)
        if any(sequences):
            if (not all(isinstance(x, tuple) and len(x) >= 6 for x in sequences)
                    or len(self.away_scored) != len(self.away_allowed)
                    or len(self.home_scored) != len(self.home_allowed)
                    or any(len(x) > 30 for x in sequences)):
                raise ValueError("Bootstrap requiere históricos completos por equipo")
            for series in sequences:
                if any(isinstance(v, bool) or not isinstance(v, (float,int))
                       or not isfinite(v) or v < 0 or v > 300 for v in series):
                    raise ValueError("Marcador histórico ESPN inválido")


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
    model_note: str = "Distribución matemática exploratoria, sin calibración validada"
    simulation_method: str = "GAUSSIANA_EXPLORATORIA"

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
    empirical = bool(scenario.away_scored)
    if empirical:
        def weights(values):
            return [0.88 ** i for i in range(len(values))]
        def empirical_mean(values):
            ws = weights(values)
            return sum(w * v for w, v in zip(ws, values)) / sum(ws)
        # Residual Gaussian variance is ONLY what the observed samples cannot
        # explain up to the requested sport-specific dispersion floor.
        hist_away_sd = sqrt((
            stdev(scenario.away_scored) ** 2 +
            stdev(scenario.home_allowed) ** 2
        ) / 2)
        hist_home_sd = sqrt((
            stdev(scenario.home_scored) ** 2 +
            stdev(scenario.away_allowed) ** 2
        ) / 2)
        residual_away = sqrt(max(0, scenario.away_sd**2-hist_away_sd**2))
        residual_home = sqrt(max(0, scenario.home_sd**2-hist_home_sd**2))
        base_away = (empirical_mean(scenario.away_scored) +
                     empirical_mean(scenario.home_allowed)) / 2
        base_home = (empirical_mean(scenario.home_scored) +
                     empirical_mean(scenario.away_allowed)) / 2
        aw_weights = weights(scenario.away_scored)
        aa_weights = weights(scenario.away_allowed)
        ho_weights = weights(scenario.home_scored)
        hd_weights = weights(scenario.home_allowed)
    correlated_scale = sqrt(1.0 - scenario.score_correlation ** 2)
    for _ in range(scenario.simulations):
        if empirical:
            a_scored = rng.choices(scenario.away_scored, weights=aw_weights)[0]
            h_allowed = rng.choices(scenario.home_allowed, weights=hd_weights)[0]
            h_scored = rng.choices(scenario.home_scored, weights=ho_weights)[0]
            a_allowed = rng.choices(scenario.away_allowed, weights=aa_weights)[0]
            # Multiplying the centered matchup sample by sqrt(2) keeps its
            # dispersion comparable to the fitted sample score variance.
            a_draw = scenario.away_mean + sqrt(2) * (
                (a_scored+h_allowed)/2 - base_away
            ) + rng.gauss(0, residual_away)
            h_draw = scenario.home_mean + sqrt(2) * (
                (h_scored+a_allowed)/2 - base_home
            ) + rng.gauss(0, residual_home)
            away, home = max(0, round(a_draw)), max(0, round(h_draw))
        else:
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
        simulation_method=("BOOTSTRAP_ESPN_RECIENTE" if empirical
                           else "GAUSSIANA_EXPLORATORIA"),
    )
