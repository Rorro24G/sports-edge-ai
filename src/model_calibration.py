"""Experimental temporal calibration of independent Sports Edge AI probabilities.

Fits a monotone Platt map from a PAST ESPN audit and evaluates on a strictly
LATER ESPN audit. A better Brier score here is NOT enough to enable this
calibrator for live picks or to claim betting returns.
"""
from __future__ import annotations

from math import exp, log
from dataclasses import dataclass


@dataclass(frozen=True)
class PlattMap:
    slope: float
    intercept: float
    training_count: int
    regularization: float

    def predict(self, p: float) -> float:
        return _sigmoid(self.slope * _logit(p) + self.intercept)


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + exp(-value))
    z = exp(value)
    return z / (1 + z)


def _logit(p: float) -> float:
    return log(p/(1-p))


def _samples(report: dict, *, min_sample: int) -> list[tuple[float, int]]:
    if report.get("data_complete") is not True:
        raise ValueError("No entrenar con registros ESPN incompletos")
    if report.get("model_validated") is not False:
        raise ValueError("Informe inválido: no es el modelo experimental")
    details = report.get("details")
    if not isinstance(details, list):
        raise ValueError("El informe necesita predicciones históricas por partido")
    pairs = []
    seen = set()
    for row in details:
        if not isinstance(row, dict):
            raise ValueError("Predicción histórica corrupta")
        event_id = str(row.get("event_id", ""))
        p = row.get("p_home_experimental")
        actual = row.get("actual_home")
        if (not event_id or event_id in seen
                or type(actual) is not bool
                or type(p) not in (int, float)
                or not .001 <= p <= .999):
            raise ValueError("Partido duplicado o predicción ESPN no utilizable")
        seen.add(event_id)
        pairs.append((float(p), int(actual)))
    if len(pairs) < min_sample:
        raise ValueError(f"Muestra insuficiente para calibración: {len(pairs)}")
    return pairs


def fit_platt(pairs: list[tuple[float, int]], *,
              regularization: float = 1.0) -> PlattMap:
    """Two-parameter convex logistic fit using Newton steps, no dependencies.

    Ridge penalty is fixed a priori (lambda=1), slope only, not intercept.
    Training outcomes may only originate from an earlier chronological period.
    """
    if regularization <= 0:
        raise ValueError("La regularización debe ser positiva")
    if len(pairs) < 30:
        raise ValueError("Se requieren al menos 30 predicciones de entrenamiento")
    x = [_logit(p) for p, _ in pairs]
    y = [actual for _, actual in pairs]
    if len(set(y)) < 2:
        raise ValueError("Entrenamiento necesita victorias y derrotas")
    slope, intercept = 1.0, 0.0
    for _ in range(40):
        probs = [_sigmoid(slope*v + intercept) for v in x]
        residual = [p-yi for p, yi in zip(probs, y)]
        weight = [p*(1-p) for p in probs]
        ga = sum(e*v for e, v in zip(residual, x)) + regularization*slope
        gb = sum(residual)
        haa = sum(w*v*v for w, v in zip(weight, x)) + regularization
        hab = sum(w*v for w, v in zip(weight, x))
        hbb = sum(weight)
        det = haa*hbb-hab*hab
        if det <= 1e-10:
            raise ValueError("No es posible ajustar esta muestra")
        da = (ga*hbb-gb*hab)/det
        db = (gb*haa-ga*hab)/det
        slope -= da
        intercept -= db
        if max(abs(da), abs(db)) < 1e-8:
            break
    if not 0 < slope < 10:
        raise ValueError("El calibrador invierte la señal o es inestable")
    return PlattMap(round(slope, 8), round(intercept, 8),
                    len(pairs), regularization)


def _metrics(pairs: list[tuple[float, int]], calibrator: PlattMap | None = None) -> dict:
    predicted = [calibrator.predict(p) if calibrator else p for p, _ in pairs]
    true = [y for _, y in pairs]
    n = len(true)
    brier = sum((p-y)**2 for p, y in zip(predicted, true))/n
    logloss = -sum(y*log(max(p, 1e-12)) + (1-y)*log(max(1-p, 1e-12))
                   for p, y in zip(predicted, true))/n
    return {"brier": round(brier, 6), "log_loss": round(logloss, 6),
            "mean_predicted_home": round(sum(predicted)/n, 5),
            "actual_home_rate": round(sum(true)/n, 5)}


def evaluate_calibration(train: dict, holdout: dict, *,
                         min_train: int = 100, min_holdout: int = 100) -> dict:
    """No future-to-past contamination, no overlap, no hyperparameter search."""
    if train.get("version") != holdout.get("version"):
        raise ValueError("Se requiere la misma versión del modelo")
    if train.get("sport") != holdout.get("sport"):
        raise ValueError("No combinar deportes en un solo calibrador")
    if train.get("source") != "ESPN scoreboard + ESPN team schedules":
        raise ValueError("Fuente de entrenamiento inesperada")
    if holdout.get("source") != train["source"]:
        raise ValueError("Fuente de prueba inesperada")
    if train["period"]["end"] >= holdout["period"]["start"]:
        raise ValueError("La evaluación debe ocurrir DESPUÉS del entrenamiento")
    fit_pairs = _samples(train, min_sample=min_train)
    test_pairs = _samples(holdout, min_sample=min_holdout)
    model = fit_platt(fit_pairs, regularization=1.0)
    raw = _metrics(test_pairs)
    calibrated = _metrics(test_pairs, model)
    return {
        "status": "EXPERIMENTO_CALIBRACION_SIN_ACTIVAR",
        "sport": train["sport"],
        "base_model": train["version"],
        "train_period": train["period"],
        "holdout_period": holdout["period"],
        "train_count": len(fit_pairs),
        "holdout_count": len(test_pairs),
        "platt_slope": model.slope,
        "platt_intercept": model.intercept,
        "regularization": model.regularization,
        "raw_holdout": raw,
        "calibrated_holdout": calibrated,
        "brier_change_calibrated_minus_raw": round(calibrated["brier"]-raw["brier"], 6),
        "fit_uses_holdout": False,
        "production_enabled": False,
        "model_validated": False,
        "return_on_investment_known": False,
        "notes": ("Calibración logística entrenada solo con temporada anterior; "
                  "la temporada posterior se usa para evaluación y no para "
                  "escoger parámetros. El resultado no acredita ganancias ni "
                  "se aplica todavía a Picks en vivo."),
    }
