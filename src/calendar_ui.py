"""Visual ESPN fixture board, no invented games or realtime status."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .live_board import CalendarSourceError

MX = ZoneInfo("America/Mexico_City")
LEAGUES = ("NBA", "NFL", "NHL")


def _source_url(url: object) -> str | None:
    if not isinstance(url, str):
        return None
    parts = urlsplit(url)
    if (parts.scheme == "https" and parts.username is None and parts.password is None
            and (parts.hostname == "espn.com"
                 or (parts.hostname or "").endswith(".espn.com"))):
        return url
    return None


def _status_label(status: str) -> str:
    value = str(status).upper()
    return {
        "PRE": "◷ POR COMENZAR", "SCHEDULED": "◷ PROGRAMADO",
        "IN": "● EN JUEGO", "POST": "✓ FINALIZADO",
        "FINAL": "✓ FINALIZADO",
    }.get(value, "● ESTADO ESPN: " + value)


def _game_card(game: dict) -> None:
    import streamlit as st
    with st.container(border=True):
        st.caption(game["sport"] + "   /   " + _status_label(game["status"]))
        st.markdown(
            "#### " + str(game["away"]) + "  **vs.**  " + str(game["home"])
        )
        time_col, venue_col = st.columns([1, 2])
        time_col.metric("Hora CDMX", str(game["local_time"]))
        venue_col.caption("DATOS DEL ENCUENTRO")
        venue_col.write("Visitante: " + str(game["away"]))
        venue_col.write("Local: " + str(game["home"]))
        if game.get("status", "").upper() in ("POST", "FINAL"):
            aw, ho = game.get("away_score"), game.get("home_score")
            if aw is not None and ho is not None:
                st.caption("Resultado ESPN: " + str(aw) + " - " + str(ho))
        verified = _source_url(game.get("source_url"))
        if verified:
            st.link_button("Ver encuentro en ESPN", verified,
                           use_container_width=True)


def render(*, board_fetch, clear_cache=None) -> None:
    import streamlit as st
    st.markdown("### Agenda deportiva")
    st.caption(
        "Selecciona una fecha y revisa cada encuentro como una ficha. "
        "Horarios locales de Ciudad de México; el estado viene de ESPN."
    )
    date_col, league_col, action_col = st.columns(
        [1.4, 1.7, 1], vertical_alignment="bottom"
    )
    with date_col:
        day = st.date_input(
            "Fecha en Ciudad de México",
            value=datetime.now(MX).date(), key="calendar_date"
        )
    with league_col:
        leagues = st.multiselect(
            "Ligas", LEAGUES, default=list(LEAGUES), key="calendar_leagues"
        )
    with action_col:
        if st.button("↻ Actualizar calendario ahora",
                     key="calendar_refresh", use_container_width=True):
            if clear_cache is not None:
                clear_cache()

    groups: dict[str, list[dict]] = {}
    rows = []
    if not leagues:
        st.info("Selecciona una liga para ver sus encuentros.")
        return

    for league in leagues:
        try:
            board = board_fetch(league, day)
        except (CalendarSourceError, OSError, ValueError):
            st.warning(
                league + ": la consulta de ESPN no está disponible. "
                "No mostraremos partidos de otro día."
            )
            continue
        found = [
            row for row in board.get("games", [])
            if row.get("sport") == league
        ]
        groups[league] = found
        st.caption(
            league + " · consulta " + str(board.get("checked_at_utc", "sin hora"))
            + " (UTC)"
        )
        for game in found:
            rows.append({
                "Liga": league, "Visitante": game.get("away", ""),
                "Local": game.get("home", ""),
                "Hora CDMX": game.get("local_time", ""),
                "Estado": game.get("status", ""),
                "Fuente": game.get("source_url", ""),
            })

    upcoming = sum(
        str(game.get("status", "")).upper() in {"PRE", "SCHEDULED"}
        for found in groups.values() for game in found
    )
    live = sum(
        str(game.get("status", "")).upper() == "IN"
        for found in groups.values() for game in found
    )
    summary = st.columns(3)
    summary[0].metric("Encuentros encontrados", len(rows))
    summary[1].metric("Por comenzar", upcoming)
    summary[2].metric("En juego", live)
    for league in leagues:
        if league not in groups:
            continue
        found = groups[league]
        st.markdown("#### " + league + " · " + str(len(found)) + " encuentros")
        if not found:
            st.info("ESPN no registró partidos de " + league + " para esa fecha.")
            continue
        for offset in range(0, len(found), 2):
            columns = st.columns(2, gap="medium")
            for i, game in enumerate(found[offset:offset + 2]):
                with columns[i]:
                    _game_card(game)

    if rows:
        with st.expander("Consultar tabla completa", expanded=False):
            st.dataframe(
                sorted(rows, key=lambda row: (row["Hora CDMX"], row["Liga"])),
                use_container_width=True, hide_index=True,
            )
    st.caption(
        "ATP/WTA aún no conectado. Si faltan datos de ESPN, "
        "no significa que el encuentro esté cancelado."
    )
