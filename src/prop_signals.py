"""Self-owned NBA player prop research from ESPN gamelogs.

Only labels a directional research signal when an explicit user/reference
line is supplied. Never invents sportsbook prices, lines, win probabilities
or recommended stakes. Every record must precede the analyzed date.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from math import isfinite
from statistics import mean,median,pstdev

from .player_props import STATS, parse_gamelog

MIN_GAMES = 7
STAT_NAMES = {"PTS":"Puntos","REB":"Rebotes","AST":"Asistencias","3PM":"Triples"}


def clean_player_series(rows: list[dict], target: date) -> list[dict]:
    """ESPN values point-in-time, deduplicated; refuse unknown dates/values."""
    seen=set()
    valid=[]
    for item in rows:
        if not isinstance(item,dict):
            continue
        try:
            d=date.fromisoformat(str(item["date"]))
            value=float(item["value"])
            event_id=str(item["event_id"])
        except (ValueError,TypeError,KeyError):
            continue
        if (d>=target or event_id in seen or not event_id or
                not isfinite(value) or not 0<=value<=120):
            continue
        seen.add(event_id)
        valid.append((d,event_id,value))
    valid.sort(key=lambda x:(x[0],x[1]),reverse=True)
    return [{"date":d.isoformat(),"event_id":eid,"value":v}
            for d,eid,v in valid[:10]]


def evaluate_prop(rows: list[dict], target: date, stat: str, *,
                  line: float | None = None) -> dict:
    if stat not in STATS:
        raise ValueError("Prop NBA no soportada")
    if line is not None and (type(line) not in (int,float) or
                            not isfinite(line) or not 0<line<=120):
        raise ValueError("Línea externa o manual inválida")
    clean=clean_player_series(rows,target)
    if len(clean)<MIN_GAMES:
        return {"status":"SIN_DATOS","games":len(clean),
                "reason":"Se requieren 7 partidos anteriores completos"}
    values=[x["value"] for x in clean]
    recent=values[:5]
    earlier=values[5:10]
    last3=mean(values[:3])
    previous=mean(values[3:7])
    momentum=last3-previous
    median10=median(values)
    average5=mean(recent)
    average10=mean(values)
    sd=pstdev(values)
    signal="SIN_LINEA"
    hit5=hit10=None
    if line is not None:
        hit5=sum(x>line for x in recent)
        hit10=sum(x>line for x in values)
        hit_under5=sum(x<line for x in recent)
        hit_under10=sum(x<line for x in values)
        # Each direction requires persistent evidence across periods and
        # a gap of at least 0.25 units beyond the input line.
        if (hit5>=4 and hit10>=7 and
                min(average5,average10,median10)>=line+.25):
            signal="TENDENCIA_OVER"
        elif (hit_under5>=4 and hit_under10>=7 and
              max(average5,average10,median10)<=line-.25):
            signal="TENDENCIA_UNDER"
        else:
            signal="PASAR"
    return {
        "status":signal,"stat":stat,"games":len(clean),
        "mean5":round(average5,2),"mean10":round(average10,2),
        "median10":round(median10,2),"std10":round(sd,2),
        "momentum_delta":round(momentum,2),
        "momentum_direction":"SUBIENDO" if momentum>=.8 else
                             "BAJANDO" if momentum<=-.8 else "ESTABLE",
        "last3":round(last3,2),"previous4":round(previous,2),
        "line":float(line) if line is not None else None,
        "over_hits_last5":hit5,"over_hits_last10":hit10,
        "recent":clean,"model_validated":False,
        "prediction_probability":None,"recommended_stake":None,
        "price":None,"source":"ESPN regular-season athlete gamelog",
    }


def player_radar(games: list[dict], target: date, *,
                 roster_fetch, gamelog_fetch,
                 per_team: int = 6, max_players: int = 12) -> dict:
    """Bounded, explicit discovery for ONE future NBA matchup.

    Does not claim all athletes were screened, and rejects injured or inactive
    players and records with too little history.
    """
    if not 1<=per_team<=8 or not 1<=max_players<=16:
        raise ValueError("Búsqueda fuera de los límites")
    if len(games)!=1 or games[0].get("sport")!="NBA":
        raise ValueError("Selecciona un solo partido NBA verificable")
    game=games[0]
    team_ids=[str(game.get(x) or "") for x in ("away_team_id","home_team_id")]
    if len(team_ids)!=2 or not all(x.isdecimal() for x in team_ids):
        raise ValueError("Faltan IDs ESPN de los equipos")
    chosen=[]
    missing=[]
    for team_id in team_ids:
        try:
            people=roster_fetch(team_id).get("athletes") or []
        except (OSError,ValueError,RuntimeError,TypeError,KeyError):
            missing.append(team_id)
            continue
        for p in people[:50]:
            if len([x for x in chosen if x["team_id"]==team_id])>=per_team:
                break
            if (not str(p.get("id") or "").isdecimal() or
                    str(p.get("team_id") or team_id)!=team_id or
                    not p.get("name") or p.get("injuries") or
                    (p.get("status") and str(p["status"]).lower() not in ("active","activo"))):
                continue
            if any(x["id"]==str(p["id"]) for x in chosen):
                continue
            chosen.append({"id":str(p["id"]),"name":p["name"],"team_id":team_id})
    chosen=chosen[:max_players]
    opportunities=[]
    failed=0
    def load(p):
        data=gamelog_fetch(p["id"],target)
        series=[]
        for stat in ("PTS","REB","AST","3PM"):
            rows=parse_gamelog(data["payload"],stat,target)
            out=evaluate_prop(rows,target,stat)
            if out["status"]=="SIN_DATOS":
                continue
            # Momentum candidates only when the last 3 games show a meaningful
            # move relative to the 4 preceding games, scaled by natural variance.
            change=out["momentum_delta"]
            threshold=max({"PTS":2.5,"REB":1.5,"AST":1.25,"3PM":.8}[stat],
                          out["std10"]*.35)
            if abs(change)<threshold:
                continue
            series.append({
                "player":p["name"],"player_id":p["id"],"team_id":p["team_id"],
                "stat":stat,"mean5":out["mean5"],"mean10":out["mean10"],
                "direction":"SUBIENDO" if change>0 else "BAJANDO",
                "momentum_delta":change,"games":out["games"],
                "score":round(abs(change)/max(1.0,out["std10"]),3),
                "event_id":str(game.get("event_id") or ""),
            })
        return series
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(load,p):p for p in chosen}
        for future in as_completed(pending):
            try:
                opportunities.extend(future.result())
            except (OSError,ValueError,RuntimeError,TypeError,KeyError):
                failed+=1
    opportunities.sort(key=lambda x:(-x["score"],x["player"],x["stat"]))
    return {
        "players_checked":len(chosen),"failed_player_histories":failed,
        "missing_rosters":missing,"ideas":opportunities[:6],
        "event_id":str(game.get("event_id") or ""),
        "status":"DESCRIPTIVO_ESPN","bookmaker_lines_used":False,
    }
