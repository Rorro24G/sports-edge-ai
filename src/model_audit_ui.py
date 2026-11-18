"""Render audited historical evidence, never as a validated betting promise."""
from __future__ import annotations

import json
from pathlib import Path

from .independent_picks import VERSION

AUDIT_PATH = Path(__file__).resolve().parents[1] / "data" / "seai_model_audit.json"


def load_model_audit(path: Path = AUDIT_PATH) -> dict | None:
    """Accept only reproducible ESPN reports for the EXACT deployed version."""
    try:
        if not path.is_file() or path.stat().st_size > 50_000:
            return None
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            return None
        if report.get("version") != VERSION:
            return None
        if report.get("source") != "ESPN scoreboard + ESPN team schedules":
            return None
        if report.get("model_validated") is not False or report.get("model_calibrated") is not False:
            return None
        if report.get("data_complete") is not True:
            return None
        n = report.get("evaluated_count")
        k = report.get("candidate_count")
        w = report.get("correct_candidates")
        if any(type(x) is not int for x in (n, k, w)):
            return None
        if not (n >= 1 and 0 <= w <= k <= n):
            return None
        if k and abs(report["candidate_accuracy_observed"] - w/k) > 0.001:
            return None
        if not (isinstance(report.get("calibration_bins"), list)
                and len(report["calibration_bins"]) == 5):
            return None
        return report
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, ZeroDivisionError):
        return None


def render_model_audit(path: Path = AUDIT_PATH) -> None:
    import streamlit as st

    report = load_model_audit(path)
    if not report:
        return
    span = report["period"]
    label = report.get("sport", "NBA")
    with st.expander("Auditoría real del cerebro · histórico ESPN", expanded=False):
        st.caption(f"{label} · {span['start']} a {span['end']} · "
                   "prueba retrospectiva con cortes anteriores a cada juego")
        left, center, right = st.columns(3)
        left.metric("Partidos evaluados", str(report["evaluated_count"]))
        center.metric("Picks experimentales", str(report["candidate_count"]))
        right.metric(
            "Acierto observado",
            f"{report['candidate_accuracy_observed']:.1%}"
            if report["candidate_count"] else "—"
        )
        st.caption(str(report["correct_candidates"]) + " aciertos entre " +
                   str(report["candidate_count"]) +
                   " selecciones. Los demás juegos se descartaron.")
        if report.get("candidate_accuracy_wilson_95"):
            lo, hi = report["candidate_accuracy_wilson_95"]
            st.caption("Intervalo Wilson 95% de la tasa observada: "
                       f"{lo:.1%} a {hi:.1%}. No predice resultados futuros.")
        a, b, c = st.columns(3)
        a.metric("Brier del modelo", f"{report['brier_all_evaluated']:.3f}")
        b.metric("Brier base 50/50", "0.250")
        home_ref = report.get("home_only_accuracy_on_candidates")
        c.metric("Solo elegir local · mismos juegos",
                 f"{home_ref:.1%}" if home_ref is not None else "—")
        st.markdown("**Calibración observada por grupos**")
        bins = report.get("calibration_bins", [])
        st.dataframe([
            {
                "Estimación local": bucket["range"],
                "Juegos": bucket["n"],
                "Prob. estimada": (f"{bucket['avg_predicted_home']:.1%}"
                                  if bucket["avg_predicted_home"] is not None else "—"),
                "Acierto real local": (f"{bucket['actual_home_frequency']:.1%}"
                                       if bucket["actual_home_frequency"] is not None else "—"),
            }
            for bucket in bins
        ], use_container_width=True, hide_index=True)
        st.caption("Hay diferencias entre probabilidades estimadas y resultados reales: "
                   "el modelo todavía NO está calibrado. No se calcularon ganancias "
                   "ni rentabilidad por faltar cuotas históricas sincronizadas.")
        url = report.get("audit_run_url", "")
        if url.startswith("https://github.com/Rorro24G/sports-edge-ai/actions/runs/"):
            st.link_button("Ver prueba y archivos auditables", url)
