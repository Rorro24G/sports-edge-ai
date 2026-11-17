"""Portada del cerebro y lectura estricta del informe de las 6:00 AM.

La información de un día anterior nunca se presenta como correspondiente a hoy.
El informe es un resumen documental de fuentes externas, no picks propios.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .pick_reference import covers_projection

MEXICO = ZoneInfo("America/Mexico_City")
LATEST = Path(__file__).resolve().parents[1] / "data" / "picks_diario.json"
BACKTEST_PATH = LATEST.parent / "picks_backtest.json"
LEAGUES = ("NBA", "NFL", "NHL")
BUILD = "CEREBRO 2.0 · NOV 2026"


def load_today_snapshot(day: date, path: Path = LATEST) -> dict | None:
    """Read a precomputed report only when its Mexico date is exactly today."""
    try:
        if not path.is_file() or path.stat().st_size > 1_500_000:
            return None
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or report.get("date_cdmx") != day.isoformat():
            return None
        stamp = datetime.fromisoformat(report["generated_at_utc"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.astimezone(MEXICO).date() != day:
            return None
        if stamp > datetime.now(timezone.utc):
            return None
        if not isinstance(report.get("leagues"), dict):
            return None
        return report
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def morning_rows(report: dict) -> list[dict]:
    """Flatten games without inventing markets, selections or outcomes."""
    if not isinstance(report, dict):
        return []
    results = []
    for league in LEAGUES:
        section = report.get("leagues", {}).get(league, {})
        for event in section.get("events", [])[:100]:
            if not isinstance(event, dict) or event.get("fecha_cdmx") != report["date_cdmx"]:
                continue
            name = str(event.get("partido", "")).strip()
            clock = str(event.get("hora_cdmx", "")).strip()
            if not name or not re.fullmatch(r"[0-2]\d:[0-5]\d", clock):
                continue
            covered = event.get("datos_covers") != "no_verificados_para_este_partido"
            ml = event.get("momios_covers") or []
            display = "Sin moneyline verificable"
            if covered and isinstance(ml, list) and len(ml) == 2 and all(ml):
                display = str(ml[0]) + " / " + str(ml[1]) + " · Covers"
            signal = covers_projection({
                "liga": league, "partido": name,
                "fecha_cdmx": report["date_cdmx"], "hora_cdmx": clock,
                "proyeccion_visitante": (event.get("proyeccion_covers") or [None, None])[0],
                "proyeccion_local": (event.get("proyeccion_covers") or [None, None])[1],
            }) if covered else None
            results.append({
                "Liga": league, "Partido": name, "Hora CDMX": clock,
                "Ganador según marcador Covers": (
                    signal["equipo_proyectado"] if signal and
                    signal["vigente_para_analisis_prepartido"] else "Sin referencia prepartido"),
                "Referencia externa": "Covers + ESPN" if event.get("espn") else (
                    "Covers" if covered else "ESPN"),
                "Moneyline": display, "Pick propio": "Sin modelo validado",
            })
    return sorted(results, key=lambda e: (e["Hora CDMX"], e["Liga"], e["Partido"]))



def morning_covers_picks(report: dict, *, now: datetime | None = None,
                         per_league: int = 3) -> list[dict]:
    """Select a short, clearly labelled *external reference* list.

    Within each league, order by projected-score difference, NOT by estimated
    win probability, expected value or profitability. Do not include started
    games, events without an identifiable Covers projection, or unverifiable
    moneyline prices.
    """
    from .pick_reference import covers_projection
    if not report or not isinstance(report.get("leagues"), dict):
        return []
    if per_league < 1:
        return []
    snapshot_day = report.get("date_cdmx")
    clock = now or datetime.now(MEXICO)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=MEXICO)
    if clock.astimezone(MEXICO).date().isoformat() != snapshot_day:
        return []
    chosen = []
    for league in LEAGUES:
        league_rows = []
        for event in report["leagues"].get(league, {}).get("events", []):
            if (not isinstance(event, dict)
                    or event.get("fecha_cdmx") != snapshot_day
                    or not event.get("fuente_covers")
                    or event.get("datos_covers") == "no_verificados_para_este_partido"):
                continue
            scores = event.get("proyeccion_covers")
            if not isinstance(scores, list) or len(scores) != 2:
                continue
            signal = covers_projection({
                "liga": league, "partido": event.get("partido"),
                "fecha_cdmx": snapshot_day, "hora_cdmx": event.get("hora_cdmx"),
                "proyeccion_visitante": scores[0],
                "proyeccion_local": scores[1],
                "momio_visitante": (event.get("momios_covers") or [None, None])[0],
                "momio_local": (event.get("momios_covers") or [None, None])[1],
                "fuente": event["fuente_covers"],
            }, now=clock)
            if not signal or not signal["vigente_para_analisis_prepartido"]:
                continue
            if not signal["momio_covers"]:
                continue
            league_rows.append({
                "Liga": league,
                "Partido": signal["partido"],
                "Hora CDMX": signal["hora_cdmx"],
                "Referencia ML (Covers)": signal["seleccion_de_referencia"],
                "Momio publicado": signal["momio_covers"],
                "Diferencia de marcador": signal["margen_proyectado"],
                "Fuente": event["fuente_covers"],
            })
        league_rows.sort(key=lambda x: (-x["Diferencia de marcador"], x["Hora CDMX"]))
        chosen.extend(league_rows[:per_league])
    return chosen

def load_backtest(day: date, path: Path = BACKTEST_PATH) -> dict | None:
    """Only load a current-day, timestamped backtest from disk."""
    try:
        if not path.is_file() or path.stat().st_size > 1_500_000:
            return None
        report = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or report.get("fecha_cdmx") != day.isoformat():
            return None
        stamp = datetime.fromisoformat(report["generado_utc"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp > datetime.now(timezone.utc):
            return None
        if not isinstance(report.get("grades"), dict):
            return None
        return report
    except (OSError, ValueError, TypeError, KeyError):
        return None


def render_reference_backtest() -> None:
    """Real scoreboard results of past Covers *references*, not model accuracy."""
    import streamlit as st

    today = datetime.now(MEXICO).date()
    data = load_backtest(today)
    with st.expander("📋 Auditoría: cómo les fue a las referencias anteriores", expanded=False):
        if data is None:
            st.info("El historial verificable empezará a acumularse cuando haya "
                    "pronósticos guardados antes del juego y ESPN publique "
                    "el resultado final. No calcularemos aciertos retroactivos "
                    "con momios obtenidos después del partido.")
            return
        count = data.get("unidades_simuladas", 0)
        st.caption("Pronósticos prepartido conservados por día, contrastados por "
                   "ID de evento con marcadores finales ESPN. "
                   "NO son las apuestas personales de tu historial.")
        if not count:
            st.info("Todavía no hay referencias terminadas y contrastadas "
                    "con suficientes datos para mostrar porcentajes.")
            return
        a, b, c, d = st.columns(4)
        a.metric("Referencias resueltas", count)
        b.metric("Acierto observado", f"{data['acierto_observado_pct']:.1f}%")
        c.metric("Resultado hipotético por unidad",
                 f"{data['beneficio_unidades']} uds.")
        d.metric("ROI histórico hipotético",
                 f"{data['roi_observado_pct']:+.1f}%")
        st.warning(
            "Estadísticas descriptivas de referencias de Covers. "
            "Una unidad hipotética por partido a precio publicado en Covers. "
            "No son dinero ganado, rentabilidad futura demostrada, "
            "picks validados ni cuotas combinables de una casa."
        )
        grades = list(data["grades"].values())
        grades.sort(key=lambda row: (row.get("fecha", ""), row.get("partido", "")),
                    reverse=True)
        rows = [{
            "Fecha": g.get("fecha"), "Liga": g.get("liga"),
            "Partido": g.get("partido"), "Referencia Covers": g.get("seleccion_covers"),
            "Momio capturado": g.get("momio_covers"), "Resultado": g.get("resultado"),
            "Marcador ESPN": g.get("resultado_espn"),
            "P&L por 1 ud.": g.get("beneficio_unidad"),
            "Fuente": g.get("fuente_espn_resultado") or g.get("fuente_espn"),
        } for g in grades[:40] if isinstance(g, dict)]
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True,
                         column_config={"Fuente": st.column_config.LinkColumn("ESPN")})
        pending = data.get("pendientes_de_verificar", 0)
        if pending:
            st.caption(f"{pending} referencias pendientes de verificación ESPN.")
        if data.get("fuentes_con_error"):
            st.caption("Algunas fechas no se pudieron contrastar; esas selecciones "
                       "no cuentan como aciertos ni pérdidas.")


def render_brain_header() -> None:
    """Static SVG/HTML and CSS motion: no scripts, user tracking or external assets."""
    import streamlit as st

    today = datetime.now(MEXICO).date()
    stamp = today.strftime("%d/%m/%Y")
    st.markdown(
        """
        <div class="brain-command">
          <div class="brain-copy">
            <div class="brain-eyebrow"><span class="brain-live"></span> SPORTS EDGE AI · CENTRO DE INTELIGENCIA</div>
            <div class="brain-heading">EL CEREBRO<br><span>DE TUS PICKS.</span></div>
            <div class="brain-description">Investiga cada partido. Contrasta las fuentes. Decide con datos, no con promesas.</div>
            <div class="brain-chips"><span>◉ ESPN</span><span>◈ COVERS</span><span>◎ MERCADOS</span><span>◉ HISTORIAL</span></div>
          </div>
          <div class="brain-art" aria-hidden="true">
            <svg viewBox="0 0 420 300" role="img" aria-label="Red neuronal abstracta">
              <defs>
                <radialGradient id="brainGlow"><stop offset="0" stop-color="#40f8a5" stop-opacity=".43"/><stop offset="1" stop-color="#40f8a5" stop-opacity="0"/></radialGradient>
                <linearGradient id="neuronEdge"><stop stop-color="#8dfdcc"/><stop offset="1" stop-color="#167a67"/></linearGradient>
              </defs>
              <ellipse cx="210" cy="150" rx="160" ry="130" fill="url(#brainGlow)"/>
              <g stroke="#3a997f" stroke-opacity=".53" stroke-width="1.5" fill="none">
                <path d="M100 158L137 80 206 49 271 86 312 149 271 224 206 257 137 221Z"/>
                <path d="M137 80L168 134 100 158 168 202 137 221M206 49L213 116 271 86 265 155 312 149M206 257L212 199 271 224 265 155 168 202 213 116 168 134 265 155M168 134L212 199"/>
                <path d="M100 158L67 118 137 80M312 149L351 185 271 224"/>
              </g>
              <g fill="#081d1c" stroke="url(#neuronEdge)" stroke-width="2">
                <circle cx="100" cy="158" r="17"/><circle cx="137" cy="80" r="16"/><circle cx="206" cy="49" r="13"/>
                <circle cx="271" cy="86" r="16"/><circle cx="312" cy="149" r="18"/><circle cx="271" cy="224" r="16"/>
                <circle cx="206" cy="257" r="13"/><circle cx="137" cy="221" r="17"/>
                <circle cx="168" cy="134" r="19"/><circle cx="213" cy="116" r="18"/>
                <circle cx="265" cy="155" r="21"/><circle cx="212" cy="199" r="20"/>
              </g>
              <g fill="#87ffd0">
                <circle cx="100" cy="158" r="5"/><circle cx="137" cy="80" r="5"/><circle cx="206" cy="49" r="4"/>
                <circle cx="271" cy="86" r="5"/><circle cx="312" cy="149" r="5"/><circle cx="271" cy="224" r="5"/>
                <circle cx="206" cy="257" r="4"/><circle cx="137" cy="221" r="5"/>
                <circle cx="168" cy="134" r="7"/><circle cx="213" cy="116" r="7"/>
                <circle cx="265" cy="155" r="7"/><circle cx="212" cy="199" r="7"/>
              </g>
              <g fill="#80ffcb"><circle cx="67" cy="118" r="4"/><circle cx="351" cy="185" r="4"/></g>
            </svg>
            <div class="brain-orbit orbit-one"></div><div class="brain-orbit orbit-two"></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"◉ {BUILD} · Jornada {stamp} (Ciudad de México) · Datos verificables, sin picks inventados")


def render_morning_snapshot() -> None:
    """Show the 6am snapshot or visibly explain why no snapshot is available."""
    import streamlit as st

    today = datetime.now(MEXICO).date()
    report = load_today_snapshot(today)
    st.markdown("#### Radar del día")
    if not report:
        st.info(
            "El informe automático de las 6:00 a. m. todavía no está disponible "
            "en esta versión o para la fecha de hoy. Puedes consultar Picks "
            "abajo: se buscarán datos actualizados bajo demanda."
        )
        return
    rows = morning_rows(report)
    groups = report["leagues"]
    cols = st.columns(4)
    for index, league in enumerate(LEAGUES):
        count = sum(row["Liga"] == league for row in rows)
        cols[index].metric(league, count, help="Partidos verificados en el informe del día")
    cols[3].metric("Picks propios validados", 0, help="Sin modelo entrenado/calibrado")
    st.caption("Informe generado " + report["generated_at_utc"] +
               " UTC · Precios sujetos a cambios.")
    st.markdown("#### Selecciones de referencia para hoy")
    selected = morning_covers_picks(report)
    if selected:
        st.caption("Hasta 3 por liga, ordenadas por diferencia de marcador proyectada. "
                   "No es una clasificación por probabilidad de acertar ni por ventaja de apuesta. "
                   "Los momios son los capturados cuando se generó el informe, "
                   "no cotizaciones en vivo.")
        public_rows = [{("Selección ML" if k == "Referencia ML (Covers)" else k): v
                        for k, v in row.items() if k != "Fuente"} for row in selected]
        st.dataframe(public_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No hay selecciones de referencia prepartido con moneyline publicado "
                "y verificable para hoy. Puedes consultar el partido en Picks "
                "o actualizar más tarde.")
    st.warning("Estos son ganadores favorecidos por los marcadores proyectados, "
               "NO picks validados de Sports Edge AI ni apuestas con rentabilidad demostrada.")
    render_reference_backtest()
    with st.expander("Abrir partidos y referencias del informe matutino", expanded=True):
        if rows:
            public_rows = [{("Equipo favorecido" if k == "Ganador según marcador Covers" else k):
                            (v.replace(" · Covers", "") if isinstance(v, str) else v)
                            for k, v in row.items() if k != "Referencia externa"} for row in rows]
            st.dataframe(public_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No se encontraron encuentros para hoy; comprueba las fuentes antes de concluir.")
    for league in LEAGUES:
        errs = groups.get(league, {}).get("errors") or []
        if errs:
            st.warning(league + ": hay fuentes que fallaron; no debe asumirse cobertura completa.")

