"""Interfaz del historial privado, con confirmación antes de escribir."""
from __future__ import annotations
import hmac
import os
import re
import streamlit as st

from .ledger_text import parse_bet_message
from .pick_ledger import add_bet, settle_bet, ledger_rows, metrics, LedgerError
from .ledger_store import initialize, read_ledger, transact, export_json, restore_backup


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, KeyError, OSError):
        value = ""
    return str(value or os.getenv(name, ""))


def render() -> None:
    st.subheader("Historial · apuestas registradas por ti")
    st.caption("Aquí solo se registran selecciones que tú confirmes. "
               "Un 5% del bank es una referencia configurable, no una obligación ni un pick automático.")
    password = _secret("LEDGER_ACCESS_PASSWORD")
    if not password:
        st.warning("El historial privado está desactivado hasta configurar LEDGER_ACCESS_PASSWORD "
                   "en los secretos de Streamlit. No se guardarán datos personales sin protección.")
        return
    path = _secret("LEDGER_DB_PATH")
    if not path:
        st.warning("No hay almacenamiento persistente configurado (LEDGER_DB_PATH). "
                   "El disco temporal de Streamlit no garantiza conservar apuestas después de reinicios.")
        return
    if not st.session_state.get("ledger_unlocked", False):
        supplied = st.text_input("Clave privada del historial", type="password",
                                 key="ledger_password")
        if st.button("Abrir historial", key="ledger_unlock"):
            if hmac.compare_digest(supplied, password):
                st.session_state["ledger_unlocked"] = True
                st.rerun()
            else:
                st.error("Clave incorrecta")
        return
    if st.button("Cerrar historial", key="ledger_logout"):
        st.session_state["ledger_unlocked"] = False
        st.session_state.pop("ledger_draft", None)
        st.rerun()
    try:
        ledger = read_ledger(path)
    except (LedgerError, OSError, ValueError) as exc:
        st.error("No se pudo leer el historial: " + str(exc))
        return
    if ledger is None:
        st.info("Primero configura el bank inicial. No se puede sobrescribir después sin una migración.")
        with st.form("initialize_bank"):
            starting = st.number_input("Bank inicial", min_value=1.0, value=1000.0, step=100.0)
            currency = st.selectbox("Moneda", ["MXN", "USD"])
            if st.form_submit_button("Crear historial"):
                try:
                    initialize(path, starting, currency)
                    st.rerun()
                except (LedgerError, OSError) as exc:
                    st.error(str(exc))
        backup = st.file_uploader("O restaura una copia JSON en un historial vacío",
                                  type=["json"], key="restore_ledger")
        if backup is not None and st.button("Confirmar restauración"):
            try:
                restore_backup(path, backup.getvalue())
                st.rerun()
            except (LedgerError, OSError) as exc:
                st.error(str(exc))
        return
    k = metrics(ledger)
    a, b, c, d = st.columns(4)
    a.metric("Bank actual", f"{k['bank_current']:.2f} {ledger['currency']}")
    b.metric("Ganancia / pérdida", f"{k['net_profit']:+.2f} ({k['pnl_pct_initial']:+.2f}%)")
    c.metric("Acierto de picks liquidados",
             f"{k['hit_rate']:.2f}%" if k["hit_rate"] is not None else "Sin datos")
    d.metric("ROI real", f"{k['roi']:.2f}%" if k["roi"] is not None else "Sin datos")
    st.caption(f"Ganados: {k['wins']} · Perdidos: {k['losses']} · Push: {k['pushes']} "
               f"· Anulados: {k['voids']} · Pendientes: {k['pending']} · "
               f"Bank disponible: {k['bank_available']:.2f} {ledger['currency']}")
    st.caption(f"Referencia 5% del bank disponible: {k['suggested_stake_5pct']:.2f} "
               f"{ledger['currency']}. La cantidad efectivamente apostada la decides tú.")

    st.markdown("**Registrar lo que decidiste apostar mediante texto**")
    message = st.text_area("Escribe tu instrucción", key="bet_command",
                           placeholder="Voy a meter NBA, partido: Lakers vs Warriors; "
                                       "pick: Lakers ML; momio: -110; con $100")
    if st.button("Interpretar instrucción", key="bet_parse"):
        try:
            st.session_state["ledger_draft"] = parse_bet_message(message)
        except LedgerError as exc:
            st.session_state.pop("ledger_draft", None)
            st.warning(str(exc))
    draft = st.session_state.get("ledger_draft")
    if draft:
        st.write("Revisa el borrador; no se ha guardado todavía:", draft)
        event_date = st.date_input("Fecha del partido", key="ledger_event_date")
        if st.button("Confirmar y guardar apuesta", key="bet_save"):
            try:
                command = dict(draft, date_cdmx=event_date.isoformat())
                transact(path, lambda data: add_bet(data, **command))
                st.session_state.pop("ledger_draft", None)
                st.success("Apuesta guardada en el historial privado")
                st.rerun()
            except (LedgerError, OSError) as exc:
                st.error(str(exc))

    pending = [b for b in ledger["bets"] if b["status"] == "pendiente"]
    if pending:
        st.markdown("**Registrar resultados (solo después de comprobarlos)**")
        chosen = st.selectbox(
            "Apuesta pendiente", [b["id"] for b in pending],
            format_func=lambda identifier: next(
                (b["sport"] + " · " + b["event"] + " · " + b["selection"]
                 + " (" + b["stake"] + ")" for b in pending if b["id"] == identifier),
                identifier),
        )
        outcome = st.selectbox("Resultado confirmado", ["ganado", "perdido", "push", "anulado"])
        if st.button("Confirmar resultado", key="bet_settle"):
            try:
                transact(path, lambda data: settle_bet(data, chosen, outcome))
                st.success("Resultado registrado")
                st.rerun()
            except (LedgerError, OSError) as exc:
                st.error(str(exc))

    if pending and st.button("Buscar resultados terminados en ESPN", key="ledger_check_results"):
        from datetime import date as parse_date
        from src.live_board import fetch_scoreboard, CalendarSourceError
        from src.pick_grading import propose_moneyline_results
        all_games = []
        dates = sorted({(bet["sport"], bet.get("event_date_cdmx"))
                        for bet in pending
                        if bet.get("sport") in ("NBA", "NFL", "NHL")
                        and bet.get("event_date_cdmx")})
        if len(dates) > 20:
            st.warning("Hay demasiadas jornadas pendientes; comprueba por fecha manualmente.")
        else:
            for league, day in dates:
                try:
                    board = fetch_scoreboard(league, parse_date.fromisoformat(day))
                    all_games.extend(board["games"])
                except (CalendarSourceError, ValueError) as exc:
                    st.warning(league + " " + day + ": ESPN no verificable (" + str(exc) + ")")
            st.session_state["ledger_grade_suggestions"] = propose_moneyline_results(
                pending, all_games
            )
    suggested = st.session_state.get("ledger_grade_suggestions", [])
    if suggested:
        st.markdown("**Resultados Moneyline detectados (requieren tu confirmación)**")
        for candidate in suggested:
            st.write(candidate["score"], " · sugerencia:", candidate["status"])
            if candidate.get("source_url"):
                st.link_button("Ver resultado en ESPN", candidate["source_url"])
            if st.button("Confirmar " + candidate["status"] + " · " +
                         candidate["bet_id"][:8], key="grade_" + candidate["bet_id"]):
                try:
                    transact(path, lambda data: settle_bet(
                        data, candidate["bet_id"], candidate["status"]))
                    st.session_state.pop("ledger_grade_suggestions", None)
                    st.rerun()
                except (LedgerError, OSError) as exc:
                    st.error(str(exc))
    rows = ledger_rows(ledger)
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("Todavía no hay apuestas confirmadas")
    st.download_button("Descargar copia completa JSON", export_json(ledger),
                       file_name="historial-privado.json", mime="application/json")
    if rows:
        import csv
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        def safe_csv_cell(value):
            if isinstance(value, str) and re.match(r"^\\s*[=+@-]", value):
                return "'" + value
            return value
        writer.writerows([{key: safe_csv_cell(value) for key, value in row.items()}
                          for row in rows])
        st.download_button("Descargar tabla CSV para Excel",
                           output.getvalue().encode("utf-8-sig"),
                           file_name="historial-picks.csv", mime="text/csv")
