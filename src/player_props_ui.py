"""UI de investigación de mercados de jugador NBA, solo fuentes trazables."""
from __future__ import annotations

from datetime import date
import streamlit as st

from .prop_review import matching_player_game, player_prop_review
from .odds_api import OddsAPIError
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
    st.caption("ESPN · historial individual de temporada regular. "
               "No hay cuota ni recomendación propia sin fuente y validación.")
    with st.spinner("Buscando el jugador en los equipos del calendario ESPN..."):
        player = resolve_player_in_games(question, games, roster_fetch=roster_fetch)
    if not player:
        st.warning("No pude identificar de forma inequívoca al jugador entre las "
                   "plantillas de NBA de esta jornada. Escribe su nombre completo "
                   "y la liga, o selecciona otra fecha.")
        return True
    st.markdown("**" + player["name"] + " · " + label.capitalize() + "**")
    st.caption("ID del deportista ESPN: " + player["id"] +
               " · Plantilla de equipo ESPN " + player["team_id"])
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
    st.caption("El porcentaje anterior es únicamente la frecuencia observada en "
               "hasta 10 juegos previos: NO representa probabilidad de acierto "
               "del próximo partido, ni EV, ni rentabilidad esperada.")
    st.dataframe(
        [{"Fecha CDMX": r["date"], "Rival": r["opponent"],
          label.capitalize(): r["value"]} for r in history[:10]],
        use_container_width=True, hide_index=True,
    )
    st.link_button("Abrir historial original ESPN",
                   "https://www.espn.com/nba/player/gamelog/_/id/" + player["id"])
    st.caption("Consulta ESPN: " + info["checked_at_utc"] +
               " UTC. Datos previos al día solicitado; pueden modificarse en origen.")
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
    st.link_button("Ver líneas y proyecciones públicas de Covers",
                   "https://www.covers.com/sport/basketball/nba/player-props")
    st.markdown("**Factores que faltan para una recomendación fiable**")
    for item in review["risk_flags"]:
        st.caption("• " + item)
    st.warning("No existe todavía probabilidad predictiva calibrada ni EV propio "
               "para este mercado. No se asigna porcentaje del bank automáticamente.")
    return True
