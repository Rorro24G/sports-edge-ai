"""Streamlit: user can obtain a grounded NBA prop signal without Covers."""
from datetime import datetime,timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest

TODAY=datetime.now(ZoneInfo("America/Mexico_City")).date()


def scoreboard(sport,day):
    return {"games":[{
        "sport":"NBA","away":"Toronto Raptors","home":"Boston Celtics",
        "away_team_id":"28","home_team_id":"2",
        "local_date":day.isoformat(),"local_time":"23:55",
        "event_id":"401390001","status":"SCHEDULED",
        "source_url":"https://www.espn.com/nba/game/_/gameId/401390001",
    }] if sport=="NBA" else [],"checked_at_utc":"2026-11-19T12:00:00Z"}


def roster(team_id):
    return {"athletes":[
        {"id":str(int(team_id)*100+1),"name":"Test Scorer "+str(team_id),
         "team_id":str(team_id),"injuries":[],"status":"Active"}
    ]}


def gamelog(player_id,target):
    values=[33,30,31,29,28,26,24,22,21,20]
    events={}
    rows=[]
    for i,pts in enumerate(values):
        ident=str(600000+i)
        events[ident]={
            "gameDate":(target-timedelta(days=i+3)).isoformat()+"T19:00:00Z",
            "opponent":{"abbreviation":"NYK"},
        }
        rows.append({"eventId":ident,
                     "stats":["35","10-20","3-8","2-2","6","5",str(pts)]})
    return {"payload":{
        "labels":["MIN","FG","3PT","FT","REB","AST","PTS"],
        "events":events,
        "seasonTypes":[{"id":"2","displayName":"Regular Season",
                        "categories":[{"events":rows}]}],
    },"source_url":"https://site.web.api.espn.com/gamelog",
       "checked_at_utc":"2026-11-19T12:00:00+00:00"}


with (
    patch("src.live_board.fetch_scoreboard",side_effect=scoreboard),
    patch("src.player_props.fetch_roster",side_effect=roster),
    patch("src.player_props.fetch_gamelog",side_effect=gamelog),
    patch("src.covers_public.fetch_public_picks",
          side_effect=AssertionError("Covers must never generate a prop")),
):
    app=AppTest.from_file("../app.py",default_timeout=40)
    app.session_state["brain_section"]="picks"
    app.session_state["picks_market_type"]="Props NBA"
    app=app.run()
    assert not app.exception,[str(x.message) for x in app.exception]
    text="\n".join(str(x.value) for x in app.markdown)
    assert "Props NBA" in text
    assert any(x.key=="props_choose_player" for x in app.button)
    assert not any(x.key=="props_run" for x in app.button)
    app=app.button(key="props_choose_player").click().run()
    assert not app.exception,[str(x.message) for x in app.exception]
    assert any(x.key=="props_run" for x in app.button)
    app=app.button(key="props_run").click().run()
    assert not app.exception,[str(x.message) for x in app.exception]
    text="\n".join(str(x.value) for x in app.markdown)
    assert "Tendencia: OVER 20.5" in text,text
    assert "Test Scorer" in text
    assert any(x.label=="Momentum reciente" for x in app.metric)
    print("ESPN_NBA_PLAYER_PROPS_UI_OK")
