"""NBA Props desk: transparent ESPN signals, with or without a quoted line."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

from .game_momentum import _dated_margin
from .live_board import CalendarSourceError
from .player_props import parse_gamelog
from .prop_signals import STAT_NAMES, evaluate_prop, player_radar

MX=ZoneInfo("America/Mexico_City")


def _rosters(game:dict, roster_fetch) -> tuple[list[dict],list[str]]:
    players=[]
    missing=[]
    for key in ("away_team_id","home_team_id"):
        team_id=str(game.get(key) or "")
        if not team_id.isdecimal():
            missing.append("Equipo sin ID ESPN")
            continue
        try:
            payload=roster_fetch(team_id)
            rows=payload.get("athletes",[])
        except (OSError,ValueError,RuntimeError,KeyError,TypeError):
            missing.append(str(team_id))
            continue
        for p in rows[:100]:
            if isinstance(p,dict) and str(p.get("id") or "").isdecimal() and p.get("name"):
                players.append({
                    "id":str(p["id"]),"name":str(p["name"]),
                    "team_id":team_id,"injuries":p.get("injuries") or [],
                    "status":p.get("status"),
                })
    names=set()
    result=[]
    for p in players:
        if p["id"] not in names:
            names.add(p["id"])
            result.append(p)
    result.sort(key=lambda p:p["name"])
    return result,missing


def render(*, board_fetch, roster_fetch, gamelog_fetch) -> None:
    st.markdown("### Props NBA")
    st.caption("Busca un jugador o detecta tendencias en sus puntos, rebotes, asistencias y triples.")
    first,second=st.columns([1,2],vertical_alignment="bottom")
    with first:
        day=st.date_input("Fecha del partido",value=datetime.now(MX).date(),
                          key="props_game_day")
    try:
        board=board_fetch("NBA",day)
    except (CalendarSourceError,ValueError,OSError,KeyError,TypeError):
        st.warning("No fue posible consultar partidos NBA en ESPN.")
        return
    games=[
        g for g in (board.get("games") or []) if isinstance(g,dict)
        and g.get("sport")=="NBA"
        and str(g.get("local_date") or day.isoformat())==day.isoformat()
        and str(g.get("status","")).upper() in ("PRE","SCHEDULED","STATUS_SCHEDULED","STATUS_PRE")
        and str(g.get("home_team_id") or "").isdigit()
        and str(g.get("away_team_id") or "").isdigit()
    ]
    if not games:
        st.info("ESPN no tiene partidos NBA pendientes para esta fecha. Prueba otro día.")
        return
    with second:
        names=[g["away"]+" vs "+g["home"]+" · "+str(g.get("local_time",""))+" CDMX"
               for g in games]
        selected=st.selectbox("Partido",names,key="props_game")
    game=games[names.index(selected)]
    identity=(day.isoformat(),str(game.get("event_id") or ""))

    a,b=st.columns(2)
    if a.button("Detectar tendencias del partido",key="props_find_trends",
                type="primary",use_container_width=True):
        with st.spinner("Contrastando gamelogs ESPN de un grupo limitado de jugadores..."):
            try:
                out=player_radar([game],day,roster_fetch=roster_fetch,
                                 gamelog_fetch=gamelog_fetch)
            except (OSError,ValueError,TypeError,RuntimeError,KeyError):
                out=None
        st.session_state["nba_prop_radar"]={"key":identity,"value":out}
    if b.button("Elegir jugador y línea",key="props_choose_player",
                use_container_width=True):
        st.session_state["nba_prop_players_open"]=identity

    saved=st.session_state.get("nba_prop_radar")
    if saved and saved.get("key")==identity:
        radar=saved.get("value")
        if radar is None:
            st.warning("No se pudo completar la consulta. Revisa la conexión ESPN.")
        elif radar["ideas"]:
            st.markdown("#### Tendencias que detectó el cerebro")
            st.caption(
                "Se evaluó una muestra limitada de " +
                str(radar["players_checked"]) + " jugadores, no toda la NBA."
            )
            for idea in radar["ideas"]:
                with st.container(border=True):
                    st.markdown("**"+idea["player"]+" · "+STAT_NAMES[idea["stat"]]+"**")
                    st.caption(
                        idea["direction"].title()+" · Últimos 5: "+
                        f"{idea['mean5']:.1f}"+" · Últimos 10: "+
                        f"{idea['mean10']:.1f}"+" · Cambio reciente: "+
                        f"{idea['momentum_delta']:+.1f}"
                    )
            st.caption("Ideas para investigar. Sin línea ni precio de casa, no hay selección Over/Under.")
        else:
            st.info(
                "El radar no encontró tendencias consistentes con los datos "
                "disponibles. Puedes analizar una línea manualmente."
            )
        if radar and radar["missing_rosters"]:
            st.caption("ESPN no entregó algunas plantillas verificables.")
    if st.session_state.get("nba_prop_players_open")==identity:
        with st.spinner("Consultando las plantillas ESPN del encuentro..."):
            players,missing=_rosters(game,roster_fetch)
        if not players:
            st.warning("ESPN no entregó jugadores verificables para los equipos.")
            return
        st.markdown("#### Analiza un prop concreto")
        person_names=[p["name"] for p in players]
        person=players[person_names.index(st.selectbox(
            "Jugador",person_names,key="props_player"
        ))]
        c,d=st.columns(2)
        with c:
            stat=st.selectbox("Estadística",list(STAT_NAMES),
                              format_func=lambda name:STAT_NAMES[name],key="props_stat")
        with d:
            line=st.number_input(
                "Línea que quieres evaluar",min_value=.5,max_value=120.5,
                value=20.5 if stat=="PTS" else 5.5 if stat in ("REB","AST") else 2.5,
                step=.5,key="props_line",
            )
        if st.button("Analizar Over / Under",key="props_run",
                     type="primary",use_container_width=True):
            with st.spinner("Contrastando la línea con resultados reales del jugador..."):
                try:
                    info=gamelog_fetch(person["id"],day)
                    rows=parse_gamelog(info["payload"],stat,day)
                    outcome=evaluate_prop(rows,day,stat,line=float(line))
                except (OSError,ValueError,RuntimeError,KeyError,TypeError):
                    outcome=None
            st.session_state["nba_prop_result"]={
                "key":identity+(person["id"],stat,float(line)),
                "result":outcome,
                "player":person,
            }
        result=st.session_state.get("nba_prop_result")
        if result and result.get("key")==identity+(person["id"],stat,float(line)):
            analysis=result.get("result")
            if not analysis:
                st.warning("ESPN no proporcionó un historial completo para esta consulta.")
            elif analysis["status"]=="SIN_DATOS":
                st.info("El jugador tiene "+str(analysis["games"])+
                        " juegos anteriores válidos; se requieren 7.")
            else:
                label={
                    "TENDENCIA_OVER":"Tendencia: OVER "+str(line),
                    "TENDENCIA_UNDER":"Tendencia: UNDER "+str(line),
                    "PASAR":"Sin ventaja histórica clara: PASAR",
                }[analysis["status"]]
                st.markdown("### "+person["name"])
                st.markdown("**"+label+" · "+STAT_NAMES[stat]+"**")
                metrics=st.columns(3)
                metrics[0].metric("Promedio últimos 5",f"{analysis['mean5']:.1f}")
                metrics[1].metric("Promedio últimos 10",f"{analysis['mean10']:.1f}")
                metrics[2].metric("Momentum reciente",f"{analysis['momentum_delta']:+.1f}")
                with st.expander("Ver partidos y cálculo",expanded=False):
                    st.dataframe([{"Fecha":x["date"],"Valor":x["value"]}
                                  for x in analysis["recent"]],
                                 use_container_width=True,hide_index=True)
                    st.caption("La línea fue escrita por ti; no es una cuota verificada.")
                    if person.get("injuries"):
                        st.warning("La plantilla ESPN contiene reportes de lesión del jugador.")
                st.link_button("Gamelog ESPN",
                    "https://www.espn.com/nba/player/gamelog/_/id/"+person["id"])
                st.caption("Lectura experimental de 7–10 partidos anteriores. "
                           "No se estimó una probabilidad ni un momio.")
