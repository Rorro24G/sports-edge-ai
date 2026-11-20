"""Display honest, source-traceable historical ESPN audits of the SAME model version."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from .independent_picks import VERSION

AUDIT_PATH = Path(__file__).resolve().parents[1] / "data" / "seai_model_audit.json"


def _verified(report: object) -> bool:
    """Reject stale versions, missing provenance, contradictions and invented outcomes."""
    if not isinstance(report, dict):
        return False
    if report.get("version") != VERSION:
        return False
    if report.get("source") != "ESPN scoreboard + ESPN team schedules":
        return False
    if report.get("model_validated") is not False or report.get("model_calibrated") is not False:
        return False
    if report.get("data_complete") is not True:
        return False
    if report.get("sport") not in ("NBA", "NFL", "NHL"):
        return False
    try:
        n, k, w = (report[x] for x in ("evaluated_count",
                                      "candidate_count", "correct_candidates"))
        if any(type(x) is not int for x in (n, k, w)):
            return False
        if n < 1 or k > n:
            return False
        if not (0 <= w <= k <= n):
            return False
        if k and abs(float(report["candidate_accuracy_observed"]) - w/k) > .001:
            return False
        if report.get("validation_status") not in (
                "AUDITORIA_DESCRIPTIVA", "MUESTRA_INSUFICIENTE"):
            return False
        period = report["period"]
        start = date.fromisoformat(period["start"])
        end = date.fromisoformat(period["end"])
        if not start <= end:
            return False
        bins = report.get("calibration_bins")
        if not isinstance(bins, list) or len(bins) != 5:
            return False
        if sum(bucket["n"] for bucket in bins) != n:
            return False
        if any(type(bucket["n"]) is not int or bucket["n"] < 0 for bucket in bins):
            return False
        brier = float(report["brier_all_evaluated"])
        if not 0 <= brier <= 1:
            return False
        if "candidate_accuracy_wilson_95" in report and k:
            lo, hi = report["candidate_accuracy_wilson_95"]
            if not 0 <= lo <= hi <= 1:
                return False
        return True
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return False


def _read(path: Path) -> object:
    if not path.is_file() or path.stat().st_size > 150_000:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def load_model_audit(path: Path = AUDIT_PATH) -> dict | None:
    """Single-report reader retained for stable testing/integration."""
    raw = _read(path)
    return raw if _verified(raw) else None


def load_model_audits(path: Path = AUDIT_PATH) -> list[dict]:
    raw = _read(path)
    if not isinstance(raw, dict):
        return []
    if raw.get("model") != VERSION or not isinstance(raw.get("reports"), list):
        return []
    reports = raw["reports"]
    if not 1 <= len(reports) <= 12 or not all(_verified(x) for x in reports):
        return []
    keys = [(x["sport"], x["period"]["start"], x["period"]["end"]) for x in reports]
    if len(set(keys)) != len(keys):
        return []
    return sorted(reports, key=lambda x: (x["sport"], x["period"]["start"]))


def load_calibration_experiment(path: Path = AUDIT_PATH) -> dict | None:
    """Only show a reproducible historical calibration that is NOT enabled."""
    raw = _read(path)
    if not isinstance(raw, dict) or raw.get("model") != VERSION:
        return None
    c = raw.get("calibration_experiment")
    if not isinstance(c, dict):
        return None
    try:
        if (c.get("status") != "EXPERIMENTO_CALIBRACION_SIN_ACTIVAR"
                or c.get("sport") != "NBA"
                or c.get("base_model") != VERSION
                or c.get("production_enabled") is not False
                or c.get("model_validated") is not False
                or c.get("fit_uses_holdout") is not False
                or c.get("train_count", 0) < 100
                or c.get("holdout_count", 0) < 100
                or c["train_period"]["end"] >= c["holdout_period"]["start"]):
            return None
        reports = load_model_audits(path)
        test = next((r for r in reports
                     if r["sport"] == "NBA"
                     and r["period"] == c["holdout_period"]), None)
        if not test:
            return None
        training = next((r for r in reports
                         if r["sport"] == "NBA"
                         and r["period"] == c["train_period"]), None)
        if (not training or training["evaluated_count"] != c["train_count"]
                or test["evaluated_count"] != c["holdout_count"]):
            return None
        before = float(c["raw_holdout"]["brier"])
        after = float(c["calibrated_holdout"]["brier"])
        if not (0 <= after <= 1 and abs(before - test["brier_all_evaluated"]) <= .0002):
            return None
        return c
    except (KeyError, TypeError, ValueError):
        return None


def load_learned_experiments(path: Path = AUDIT_PATH) -> list[dict]:
    """Only expose independent ESPN experiments with matching source audits."""
    root = _read(path)
    if not isinstance(root, dict) or root.get("model") != VERSION:
        return []
    experiment = root.get("learned_challengers")
    if not isinstance(experiment, dict):
        return []
    if (experiment.get("trained_model") != "SEAI-APRENDIZAJE-0.1"
            or experiment.get("production_enabled") is not False):
        return []
    results = experiment.get("results")
    if not isinstance(results, list) or not 1 <= len(results) <= 3:
        return []
    reports = load_model_audits(path)
    seen = set()
    for item in results:
        try:
            sport = item["sport"]
            if (sport not in ("NBA", "NHL", "NFL") or sport in seen
                    or item["base_model"] != VERSION
                    or item["trained_model"] != experiment["trained_model"]
                    or item.get("production_enabled") is not False
                    or item.get("used_covers_to_train") is not False
                    or item.get("train_uses_holdout") is not False
                    or item.get("model_validated") is not False
                    or item["train_period"]["end"] >= item["holdout_period"]["start"]):
                return []
            seen.add(sport)
            early = next((r for r in reports if
                          r["sport"] == sport and r["period"] == item["train_period"]), None)
            late = next((r for r in reports if
                         r["sport"] == sport and r["period"] == item["holdout_period"]), None)
            if (early is None or late is None
                    or early["evaluated_count"] != item["train_count"]
                    or late["evaluated_count"] != item["holdout_count"]):
                return []
            baseline = float(item["old_model_holdout"]["brier"])
            learned = float(item["learned_model_holdout"]["brier"])
            delta = float(item["brier_delta_learned_minus_old"])
            if (not 0 <= baseline <= 1 or not 0 <= learned <= 1
                    or abs(baseline-late["brier_all_evaluated"]) > 0.0002
                    or abs(learned-baseline-delta) > 0.0002):
                return []
        except (KeyError, TypeError, ValueError):
            return []
    return sorted(results, key=lambda x:x["sport"])


def render_model_audit(path: Path = AUDIT_PATH) -> None:
    import streamlit as st

    reports = load_model_audits(path)
    if not reports:
        single = load_model_audit(path)
        if single:
            reports = [single]
    if not reports:
        return
    with st.expander("Pruebas reales del cerebro · ESPN", expanded=False):
        st.caption("Evaluación retrospectiva sin usar resultados futuros para "
                   "cada predicción. Misma versión del motor; temporadas separadas.")
        recent = {}
        for report in reports:
            recent[report["sport"]] = report
        cols = st.columns(3)
        for col, sport in zip(cols, ("NBA", "NFL", "NHL")):
            if sport not in recent:
                continue
            r = recent[sport]
            col.metric(sport + " · acierto histórico",
                       f"{r['candidate_accuracy_observed']:.1%}" if r["candidate_count"] else "—")
            col.caption(str(r["correct_candidates"]) + "/" +
                        str(r["candidate_count"]) + " candidatos · " +
                        r["period"]["end"][:4])
        st.markdown("**Resultados por temporada, sin mezclar muestras**")
        st.dataframe([
            {
                "Liga": r["sport"],
                "Año": r["period"]["end"][:4],
                "Evaluados": r["evaluated_count"],
                "Selecciones": r["candidate_count"],
                "Aciertos": r["correct_candidates"],
                "Acierto observado": (f"{r['candidate_accuracy_observed']:.1%}"
                                      if r["candidate_count"] else "—"),
                "Brier": f"{r['brier_all_evaluated']:.3f}",
                "Calidad de muestra": (
                    "Limitada" if r["validation_status"] == "MUESTRA_INSUFICIENTE"
                    else "Auditoría descriptiva"
                ),
            }
            for r in sorted(reports, key=lambda r: (r["sport"], r["period"]["start"]))
        ], use_container_width=True, hide_index=True)
        st.caption("Brier menor es mejor; la referencia constante 50/50 equivale "
                   "a 0.250. No es comparación con el favorito de una casa. "
                   "No disponemos aquí de cuotas históricas alineadas para medir EV/ROI.")
        if any(r["brier_all_evaluated"] >= .25 for r in reports):
            st.caption("Algunas muestras NO superan la referencia Brier 0.250; "
                       "esas señales requieren precaución especial.")
        experiment = load_calibration_experiment(path)
        if experiment:
            old = experiment["raw_holdout"]["brier"]
            new = experiment["calibrated_holdout"]["brier"]
            st.markdown("**Calibración experimental NBA · 2025 frente a 2026**")
            st.caption(
                f"Brier sin ajuste: {old:.4f} · ajuste temporal: {new:.4f}. "
                "El cambio es pequeño; no está activado en Picks ni valida "
                "retornos de apuestas."
            )
        learned = load_learned_experiments(path)
        if learned:
            st.markdown("**Nuevo cerebro entrenado · solo laboratorio**")
            st.dataframe([
                {
                    "Liga": x["sport"],
                    "Entrenó con": x["train_period"]["end"][:4],
                    "Probado en": x["holdout_period"]["end"][:4],
                    "Brier actual": f"{x['old_model_holdout']['brier']:.4f}",
                    "Brier aprendido": f"{x['learned_model_holdout']['brier']:.4f}",
                    "Juicio": ("Mejoró" if x["brier_delta_learned_minus_old"] < 0
                               else "Empeoró · no promover"),
                }
                for x in learned
            ], hide_index=True, use_container_width=True)
            st.caption("Aprendió pesos propios de forma, ataque, defensa, descanso "
                       "y localía con ESPN 2025. Se evaluó sobre 2026 sin "
                       "reentrenamiento. Las mejoras son pequeñas; NHL empeoró. "
                       "Sigue completamente DESACTIVADO para los picks publicados.")
        st.caption("Este motor todavía NO está entrenado/calibrado para producción "
                   "ni tiene rentabilidad validada. Los intervalos de acierto no son "
                   "probabilidades de éxito de futuras apuestas.")
        urls = [
            r.get("audit_run_url", "") for r in reports
            if r.get("audit_run_url", "").startswith(
                "https://github.com/Rorro24G/sports-edge-ai/actions/runs/"
            )
        ]
        if urls:
            st.link_button("Ver ejecución y auditoría ESPN", urls[-1])
