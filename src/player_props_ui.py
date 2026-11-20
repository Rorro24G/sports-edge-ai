"""UI de investigación de mercados de jugador NBA, solo fuentes trazables."""
from __future__ import annotations

from datetime import date
import streamlit as st

from .prop_review import matching_player_game, player_prop_review
from .odds_api import OddsAPIError
from .prop_signals import evaluate_prop
from .player_props import (
    PlayerSourceError, fetch_gamelog, fetch_roster, parse_gamelog,
    parse_player_question, resolve_player_in_games, summarize_prop,
)


def render_player_research(question: str, day: date, *,
                           games: list[dict],
                           roster_fetch=fetch_roster,
                           gamelog_fetch=fetch_gamelog,
                           prop_odds_fetch=None, prop_api_key: str = "") -> bool:
    """Returns True when a player-stat query was handled."""
    request = parse_player_question(question)
    if request is None:
        return False
    st.markdown("### Análisis de jugador · NBA")
    label = {"PTS": "puntos", "REB": "rebotes", "AST": "asistencias",
             "3PM": "triples anotados"}[request.stat]
    st.caption("Historial ESPN · NBA")
    with st.spinner("Buscando el jugador en los equipos del calendario ESPN..."):
        player = resolve_player_in_games(question, games, roster_fetch=roster_fetch)
    if not player:
        st.warning("No pude identificar de forma inequívoca al jugador entre las "
                   "plantillas de NBA de esta jornada. Escribe su nombre completo "
                   "y la liga, o selecciona otra fecha.")
        return True
    st.markdown("**" + player["name"] + " · " + label.capitalize() + "**")
    st.caption("Estadísticas verificadas de la temporada regular.")
    if player.get("injuries"):
        st.warning("ESPN publica reportes de lesiones para este jugador. "
                   "Verifica su disponibilidad antes del partido.")
        with st.expander("Reportes de lesión de la plantilla ESPN"):
            for injury in player["injuries"][:5]:
                if isinstance(injury, dict):
                    st.write(injury.get("status") or injury.get("details")
                             or injury.get("type") or "Detalle no informado")
    try:
        info = gamelog_fetch(player["id"], day)
        history = parse_gamelog(info["payload"], request.stat, day)
    except (PlayerSourceError, OSError, ValueError, KeyError, TypeError) as exc:
        st.warning("No se pudo verificar el historial ESPN: " + str(exc))
        return True
    if not history:
        st.info("ESPN no entregó suficientes partidos de temporada regular anteriores "
                "a esta fecha para evaluar " + label + ". No se inventará un promedio.")
        st.link_button("Consultar registros en ESPN",
                       "https://www.espn.com/nba/player/gamelog/_/id/" + player["id"])
        return True
    matching_game = matching_player_game(player, games, day)
    offers = []
    if (prop_api_key and prop_odds_fetch and matching_game
            and request.line is not None and request.direction):
        try:
            offers = prop_odds_fetch(
                prop_api_key, matching_game, day, player["name"],
                request.stat, request.direction, request.line,
            )
        except (OddsAPIError, ValueError, TypeError) as exc:
            st.caption("El proveedor de momios no pudo verificar esta línea. "
                       "No se mostrarán precios sin confirmación.")
    review = player_prop_review(player, history, request,
                                game=matching_game, offers=offers)
    stat = summarize_prop(history, request)
    own_signal = evaluate_prop(history, day, request.stat, line=request.line)
    if own_signal.get("status") in ("TENDENCIA_OVER", "TENDENCIA_UNDER"):
        direction_name = own_signal["status"].replace("TENDENCIA_", "").title()
        st.markdown("**Señal del cerebro: " + direction_name + " " +
                    str(request.line) + " · " + label + "**")
        if request.direction and request.direction != direction_name.lower():
            st.caption("Contradice la dirección que preguntaste.")
    elif request.line is not None and own_signal.get("status") == "PASAR":
        st.markdown("**Señal del cerebro: PASAR**")
    a, b, c = st.columns(3)
    a.metric("Promedio últimos 5", f"{stat['last5']:.1f} {label}")
    b.metric("Promedio últimos 10", f"{stat['last10']:.1f} {label}")
    c.metric("Juegos anteriores con dato", stat["games"])
    if request.line is not None and request.direction:
        direction = "Over" if request.direction == "over" else "Under"
        st.markdown("**" + direction + " " + str(request.line).rstrip("0").rstrip(".")
                    + " " + label + "**")
        hits = stat["historical_hits"]
        count = stat["historical_sample"]
        rate = stat["historical_rate"]
        if count:
            st.metric("Veces que cumplió en los últimos 10 registros",
                      f"{hits} de {count} ({rate:.1f}%)")
            if stat["pushes"]:
                st.caption(f"Pushes históricos excluidos del porcentaje: {stat['pushes']}")
        else:
            st.info("Todos los resultados fueron pushes: sin tasa histórica calculable.")
    else:
        st.info("Para comparar un Over/Under escribe una línea exacta, "
                "por ejemplo «over de 24.5 puntos de " + player["name"] + "».")
    st.caption("Frecuencia observada en hasta 10 juegos anteriores; no es probabilidad futura.")
    st.dataframe(
        [{"Fecha CDMX": r["date"], "Rival": r["opponent"],
          label.capitalize(): r["value"]} for r in history[:10]],
        use_container_width=True, hide_index=True,
    )
    st.link_button("Abrir historial original ESPN",
                   "https://www.espn.com/nba/player/gamelog/_/id/" + player["id"])
    with st.expander("Datos de la consulta ESPN", expanded=False):
        st.caption("Consultado " + info["checked_at_utc"] + " UTC")
    if offers:
        st.markdown("**Momios para exactamente este jugador, línea y mercado**")
        st.dataframe([
            {"Casa": o["casa"], "Selección": o["direccion"].title(),
             "Línea": o["linea"], "Momio americano": o["momio_americano"],
             "Actualización UTC": o["actualizado_utc"],
             "Proveedor": o["fuente"]}
            for o in offers
        ], hide_index=True, use_container_width=True)
        st.caption("Precios publicados por el proveedor y sujetos a cambios. "
                   "Comprobarlos en la casa antes de apostar.")
    with st.expander("Limitaciones de este análisis", expanded=False):
        for item in review["risk_flags"]:
            st.caption("• " + item)
    st.caption("Modelo experimental sin calibración para props ni importe recomendado.")
    return True
