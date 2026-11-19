"""ESPN-only momentum context: pregame form and observed play-by-play.

Momentum is a descriptive score trend, NOT a win-probability model.
Live play-by-play is shown only on demand, never used for a pregame pick.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from statistics import mean
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import re


def _dated_margin(games: list[dict], target: date) -> list[float]:
    found = []
    seen = set()
    for g in games:
        if not isinstance(g, dict):
            continue
        try:
            when = date.fromisoformat(str(g["date"]))
            key = str(g["event_id"])
            pf, pa = float(g["points_for"]), float(g["points_against"])
        except (TypeError, ValueError, KeyError):
            continue
        if (not key or key in seen or when >= target or not isfinite(pf)
                or not isfinite(pa) or not 0 <= pf <= 300 or not 0 <= pa <= 300):
            continue
        seen.add(key)
        found.append((when, key, pf-pa))
    found.sort(key=lambda x:(x[0], x[1]),reverse=True)
    return [x[2] for x in found[:10]]


def historical_momentum(games: list[dict], target: date) -> dict | None:
    """A team's last 3 games vs the previous 4, strictly before target."""
    margins = _dated_margin(games, target)
    if len(margins) < 7:
        return None
    last3 = mean(margins[:3])
    previous4 = mean(margins[3:7])
    delta = last3-previous4
    label = "SUBIENDO" if delta >= 3 else "BAJANDO" if delta <= -3 else "ESTABLE"
    return {
        "direction": label, "delta": round(delta, 2),
        "last3_margin": round(last3, 2),
        "previous4_margin": round(previous4, 2),
        "sample": 7,
        "source": "ESPN completed team games before event",
    }


def matchup_momentum(away_games: list[dict], home_games: list[dict],
                     target: date) -> dict:
    """No inference when either team's historical series is insufficient."""
    away=historical_momentum(away_games,target)
    home=historical_momentum(home_games,target)
    return {"away":away,"home":home,"status":"CON_DATOS" if away and home else "SIN_DATOS"}


def parse_plays(payload: dict, event_id: str, *, limit: int = 6) -> list[dict]:
    """Parse ESPN NBA game summary plays. Reject unrelated events and scores."""
    if not isinstance(payload,dict) or not re.fullmatch(r"\d{5,15}",str(event_id)):
        return []
    # The summary header must explicitly identify the same event. Never
    # accidentally display highlights of a different game.
    head = payload.get("header") or {}
    competitions = head.get("competitions") or []
    confirmed = str(head.get("id") or "")
    if not confirmed and competitions and isinstance(competitions[0],dict):
        confirmed = str(competitions[0].get("id") or "")
    if confirmed != str(event_id):
        return []
    entries = payload.get("plays") or []
    if isinstance(entries,dict):
        entries = entries.get("allPlays") or entries.get("plays") or []
    if not isinstance(entries,list):
        return []
    latest=[]
    for play in entries[-300:]:
        if not isinstance(play,dict):
            continue
        text = play.get("text") or play.get("shortText") or ""
        if not isinstance(text,str) or not text.strip():
            continue
        away,home=play.get("awayScore"),play.get("homeScore")
        if type(away) not in (int,float) or type(home) not in (int,float):
            continue
        if not all(isfinite(x) and 0<=x<=300 for x in (away,home)):
            continue
        period=play.get("period") or {}
        clock=play.get("clock") or {}
        latest.append({
            "text":text.strip()[:180],
            "period":str(period.get("number","")) if isinstance(period,dict) else "",
            "clock":str(clock.get("displayValue","")) if isinstance(clock,dict) else "",
            "away_score":int(away),"home_score":int(home),
        })
    return latest[-limit:] if 1<=limit<=12 else []


def play_run(plays: list[dict]) -> dict | None:
    """Observe NET score change across a sequence, not make a prediction."""
    if len(plays)<2:
        return None
    first,last=plays[0],plays[-1]
    scored_away=last["away_score"]-first["away_score"]
    scored_home=last["home_score"]-first["home_score"]
    if min(scored_home,scored_away)<0:
        return None
    return {
        "away_points":scored_away,"home_points":scored_home,
        "lead": "LOCAL" if scored_home>scored_away else "VISITANTE"
                if scored_away>scored_home else "IGUALADO",
        "label": f"Últimas jugadas con marcador: local +{scored_home}, visitante +{scored_away}",
    }


def fetch_game_plays(event_id: str) -> dict:
    """NBA public ESPN summary, fetched only for a user-selected exact event."""
    if not re.fullmatch(r"\d{5,15}",str(event_id)):
        raise ValueError("Evento NBA no válido")
    url=("https://site.api.espn.com/apis/site/v2/sports/"
         "basketball/nba/summary?event="+str(event_id))
    req=Request(url,headers={"Accept":"application/json",
                             "User-Agent":"SportsEdgeAI-personal/1.0"})
    try:
        with urlopen(req,timeout=12) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000:
            raise ValueError("Respuesta demasiado grande")
        payload=json.loads(raw)
    except (HTTPError,URLError,OSError,TimeoutError,ValueError):
        raise ValueError("ESPN no entregó jugadas verificables") from None
    recent=parse_plays(payload,str(event_id))
    return {"plays":recent,"run":play_run(recent),
            "source_url":"https://www.espn.com/nba/playbyplay/_/gameId/"+str(event_id),
            "checked_at_utc":datetime.now(timezone.utc).isoformat()}
