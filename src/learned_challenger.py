"""Sports Edge AI 3.0: independently trained challenger, ESPN data only.

Creates point-in-time features for games and learns logistic coefficients from
an earlier season. No Covers prices/projections/consensus ever enter features.
This is a SHADOW challenger; it cannot replace the live Picks model without a
separate, prospective evaluation and explicit release change.
"""
from __future__ import annotations

from datetime import date
from math import exp, isfinite, log, sqrt
from statistics import mean, pstdev, stdev

from .independent_picks import SPEC, _history

FEATURE_KEYS = (
    "form_gap", "recent_form_gap", "offense_gap", "defense_gap",
    "trend_gap", "winrate_gap", "rest_gap", "venue_gap", "volatility_gap",
)
SPORT_SCORE_SCALE = {"NBA": 14.0, "NFL": 11.0, "NHL": 2.8}
TRAINING_VERSION = "SEAI-APRENDIZAJE-0.1"


def _avg(values: list[float]) -> float:
    ws = [.85 ** i for i in range(len(values))]
    return sum(v * w for v, w in zip(values, ws)) / sum(ws)


def _form(games: list[dict]) -> list[float]:
    return [float(g["points_for"])-float(g["points_against"]) for g in games]


def _days_off(games: list[dict], day: date) -> int:
    return min(6, max(0, (day - date.fromisoformat(games[0]["date"])).days - 1))


def extract_features(sport: str, away_data: dict, home_data: dict,
                     target: date) -> dict | None:
    """Reject futures and tiny samples BEFORE producing numeric features."""
    if sport not in SPEC or type(target) is not date:
        return None
    cfg = SPEC[sport]
    away = _history(away_data, target, cfg["window"])
    home = _history(home_data, target, cfg["window"])
    if min(len(away), len(home)) < cfg["min_games"]:
        return None
    scale = SPORT_SCORE_SCALE[sport]
    af, hf = _form(away), _form(home)
    win_away = sum(x > 0 for x in af)/len(af)
    win_home = sum(x > 0 for x in hf)/len(hf)
    recent_away, recent_home = af[:5], hf[:5]
    def trend(values: list[float]) -> float:
        return _avg(values[:3]) - _avg(values[3:7])
    away_venue = [g for g in away if g.get("home") is False]
    home_venue = [g for g in home if g.get("home") is True]
    venue_gap = (
        (_avg([float(g["points_for"]) for g in home_venue])
         - _avg([float(g["points_for"]) for g in away_venue]))/scale
        if len(away_venue) >= 3 and len(home_venue) >= 3 else 0.0
    )
    features = {
        "form_gap": (_avg(hf)-_avg(af))/scale,
        "recent_form_gap": (_avg(recent_home)-_avg(recent_away))/scale,
        "offense_gap": (
            _avg([g["points_for"] for g in home])
            - _avg([g["points_for"] for g in away]))/scale,
        "defense_gap": (
            _avg([g["points_against"] for g in away])
            - _avg([g["points_against"] for g in home]))/scale,
        "trend_gap": (trend(hf)-trend(af))/scale,
        "winrate_gap": win_home-win_away,
        "rest_gap": (_days_off(home, target)-_days_off(away, target))/3.0,
        "venue_gap": venue_gap,
        "volatility_gap": (stdev(af)-stdev(hf))/scale,
    }
    if any(not isfinite(x) or abs(x)>1000 for x in features.values()):
        return None
    observed = [g["date"] for g in away+home]
    return {
        "features": {name: round(features[name], 6) for name in FEATURE_KEYS},
        "max_history_date": max(observed),
        "away_games": len(away), "home_games": len(home),
        "feature_version": TRAINING_VERSION,
        "data_source": "ESPN past team results only",
    }


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1/(1+exp(-min(z, 40)))
    e = exp(max(z, -40))
    return e/(1+e)


def _score(x: list[float], w: list[float], b: float) -> float:
    return _sigmoid(b+sum(xi*wi for xi, wi in zip(x, w)))


def _samples(report: dict, limit: int) -> list[dict]:
    if (report.get("data_complete") is not True
            or report.get("model_calibrated") is not False
            or report.get("model_validated") is not False
            or report.get("source") != "ESPN scoreboard + ESPN team schedules"):
        raise ValueError("Auditoría ESPN incompleta o sin procedencia")
    details = report.get("details")
    if not isinstance(details, list):
        raise ValueError("Se necesitan eventos auditables")
    result, ids = [], set()
    for row in details:
        if not isinstance(row, dict):
            raise ValueError("Evento mal formado")
        eid = str(row.get("event_id", ""))
        raw_features = row.get("pregame_features")
        outcome = row.get("actual_home")
        if raw_features is None:
            continue  # Insufficient history; never invent a training row
        if (not eid or eid in ids or type(outcome) is not bool
                or not isinstance(raw_features, dict)
                or set(raw_features) != set(FEATURE_KEYS)):
            raise ValueError("Datos duplicados o características inválidas")
        day = date.fromisoformat(row["date"])
        if not date.fromisoformat(row["last_feature_date"]) < day:
            raise ValueError("FUGA DE DATOS: característica posterior al juego")
        values = []
        for key in FEATURE_KEYS:
            value = raw_features[key]
            if type(value) not in (float, int) or not isfinite(value) or abs(value)>1000:
                raise ValueError("Característica no numérica/finita")
            values.append(float(value))
        baseline = row["p_home_experimental"]
        if type(baseline) not in (float, int) or not .001 <= baseline <= .999:
            raise ValueError("Probabilidad base inválida")
        ids.add(eid)
        result.append({
            "event_id": eid, "date": day, "x": values,
            "y": int(outcome), "baseline": float(baseline),
        })
    if len(result) < limit:
        raise ValueError(f"Muestra insuficiente para entrenamiento/prueba: {len(result)}")
    return result


def _metrics(rows: list[dict], probabilities: list[float]) -> dict:
    n = len(rows)
    brier = sum((p-row["y"])**2 for p, row in zip(probabilities, rows))/n
    logloss = -sum(
        row["y"]*log(max(.000001, p))+(1-row["y"])*log(max(.000001, 1-p))
        for p, row in zip(probabilities, rows)
    )/n
    correct = sum((p > .5) == bool(row["y"]) for p, row in zip(probabilities, rows))
    return {
        "brier": round(brier, 6),
        "log_loss": round(logloss, 6),
        "winner_accuracy": round(correct/n, 5),
        "mean_home_probability": round(mean(probabilities), 5),
        "home_win_frequency": round(mean(row["y"] for row in rows), 5),
    }


def learn_weights(train_rows: list[dict], *, ridge: float = .12) -> dict:
    """Train-only standardization and deterministic ridge logistic regression."""
    if len(train_rows) < 100 or not 0.01 <= ridge <= 10:
        raise ValueError("Entrenamiento insuficiente o regularización fuera de rango")
    p = len(FEATURE_KEYS)
    means = [mean(r["x"][j] for r in train_rows) for j in range(p)]
    scales = [max(.10, pstdev(r["x"][j] for r in train_rows)) for j in range(p)]
    def normalize(row):
        return [max(-5, min(5, (row["x"][j]-means[j])/scales[j]))
                for j in range(p)]
    xs = [normalize(row) for row in train_rows]
    ys = [row["y"] for row in train_rows]
    if min(sum(ys), len(ys)-sum(ys)) < 15:
        raise ValueError("La muestra carece de suficientes victorias o derrotas")
    w = [0.0]*p
    home_rate = min(.99, max(.01, mean(ys)))
    bias = log(home_rate/(1-home_rate))
    n = len(xs)
    for _ in range(1200):
        residual = [_score(x, w, bias)-y for x, y in zip(xs, ys)]
        grads = [
            sum(e*x[j] for e, x in zip(residual, xs))/n + ridge*w[j]
            for j in range(p)
        ]
        gb = mean(residual)
        rate = .15
        w = [max(-8, min(8, value-rate*g)) for value, g in zip(w, grads)]
        bias -= rate*gb
    return {
        "feature_names": list(FEATURE_KEYS),
        "weights": [round(value, 9) for value in w],
        "intercept": round(bias, 9),
        "means": [round(value, 9) for value in means],
        "scales": [round(value, 9) for value in scales],
        "ridge": ridge,
        "training_rows": n,
        "feature_version": TRAINING_VERSION,
    }


def infer(model: dict, features: dict) -> float:
    if (model.get("feature_names") != list(FEATURE_KEYS)
            or model.get("feature_version") != TRAINING_VERSION
            or set(features) != set(FEATURE_KEYS)):
        raise ValueError("Versión o columnas del modelo no compatibles")
    values = [features[k] for k in FEATURE_KEYS]
    normalized = [
        max(-5, min(5, (float(x)-m)/sd))
        for x, m, sd in zip(values, model["means"], model["scales"])
    ]
    return _score(normalized, model["weights"], model["intercept"])


def train_and_compare(train: dict, holdout: dict, *,
                      min_train: int = 100, min_holdout: int = 100) -> dict:
    """One locked 2025→2026 comparison; never choose settings on the holdout."""
    if train.get("sport") != holdout.get("sport"):
        raise ValueError("Se requieren modelos separados por deporte")
    if train.get("version") != holdout.get("version"):
        raise ValueError("No mezclar versiones del modelo base")
    if train["period"]["end"] >= holdout["period"]["start"]:
        raise ValueError("La temporada de entrenamiento debe preceder la prueba")
    earlier = _samples(train, min_train)
    later = _samples(holdout, min_holdout)
    train_ids, holdout_ids = {r["event_id"] for r in earlier}, {r["event_id"] for r in later}
    if train_ids & holdout_ids:
        raise ValueError("Fuga: mismos encuentros presentes en ambos periodos")
    model = learn_weights(earlier, ridge=.12)
    new_probs = [infer(model, dict(zip(FEATURE_KEYS, row["x"]))) for row in later]
    baseline = [row["baseline"] for row in later]
    new_metrics = _metrics(later, new_probs)
    base_metrics = _metrics(later, baseline)
    return {
        "status": "CHALLENGER_ENTRENADO_EN_SOMBRA",
        "trained_model": TRAINING_VERSION,
        "base_model": train["version"],
        "sport": train["sport"],
        "train_period": train["period"],
        "holdout_period": holdout["period"],
        "train_count": len(earlier),
        "holdout_count": len(later),
        "model": model,
        "old_model_holdout": base_metrics,
        "learned_model_holdout": new_metrics,
        "brier_delta_learned_minus_old": round(new_metrics["brier"]-base_metrics["brier"], 6),
        "logloss_delta_learned_minus_old": round(new_metrics["log_loss"]-base_metrics["log_loss"], 6),
        "train_uses_holdout": False,
        "used_covers_to_train": False,
        "production_enabled": False,
        "model_validated": False,
        "notes": (
            "Challenger entrenado con ESPN 2025 y contrastado en ESPN 2026; "
            "hiperparámetros fijos antes de comprobar la muestra posterior. "
            "No es validación prospectiva ni ROI de apuestas."
        ),
    }
