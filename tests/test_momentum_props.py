"""Factual ESPN momentum and props: strictly pregame, no invented market."""
from datetime import date,timedelta
from unittest import TestCase

from src.game_momentum import historical_momentum, matchup_momentum, parse_plays, play_run
from src.prop_signals import evaluate_prop, player_radar, clean_player_series

DAY=date(2026,11,19)


def hist(values, *, future=False):
    rows=[{"date":(DAY-timedelta(days=i+1)).isoformat(),
           "event_id":str(800+i),"points_for":120+v,
           "points_against":120,"home":i%2==0}
          for i,v in enumerate(values)]
    if future:
        rows.append({"date":DAY.isoformat(),"event_id":"999",
                     "points_for":200,"points_against":0})
    return rows


def stats(values, *, future=False):
    rows=[{"date":(DAY-timedelta(days=i+1)).isoformat(),
           "event_id":str(500+i),"value":v} for i,v in enumerate(values)]
    if future:
        rows.append({"date":DAY.isoformat(),"event_id":"999","value":100.})
    return rows


class MomentumAndPropsTests(TestCase):
    def test_team_momentum_is_seven_prior_completed_games_only(self):
        values=[10,8,9,-2,-3,-1,0]
        a=historical_momentum(hist(values),DAY)
        b=historical_momentum(hist(values,future=True),DAY)
        self.assertEqual(a,b)
        self.assertEqual(a["direction"],"SUBIENDO")
        self.assertEqual(a["sample"],7)
        self.assertGreater(a["delta"],10)
        self.assertIsNone(historical_momentum(hist([1,2,3]),DAY))
        self.assertEqual(matchup_momentum(hist(values),hist([-v for v in values]),DAY)["status"],
                         "CON_DATOS")

    def test_props_need_exact_user_line_and_seven_earlier_games(self):
        values=[28,27,28,29,26,26,25,21,20,19]
        no_line=evaluate_prop(stats(values),DAY,"PTS")
        self.assertEqual(no_line["status"],"SIN_LINEA")
        self.assertIsNone(no_line["prediction_probability"])
        over=evaluate_prop(stats(values,future=True),DAY,"PTS",line=24.5)
        self.assertEqual(over["status"],"TENDENCIA_OVER")
        self.assertEqual(over["over_hits_last10"],7)
        self.assertEqual(over["over_hits_last5"],5)
        self.assertEqual(over["recent"],no_line["recent"])
        self.assertEqual(over["momentum_direction"],"SUBIENDO")
        under=evaluate_prop(stats([5,4,4,3,5,6,6,10,11,12]),DAY,"REB",line=7.5)
        self.assertEqual(under["status"],"TENDENCIA_UNDER")
        self.assertEqual(evaluate_prop(stats(values),DAY,"PTS",line=25.5)["status"],"PASAR")
        self.assertEqual(evaluate_prop(stats(values[:5]),DAY,"PTS",line=24.5)["status"],"SIN_DATOS")

    def test_reject_invalid_prop_lines_and_duplicates(self):
        with self.assertRaises(ValueError):
            evaluate_prop(stats([1]*10),DAY,"PTS",line=-2)
        with self.assertRaises(ValueError):
            evaluate_prop(stats([1]*10),DAY,"ML",line=2.5)
        with self.assertRaises(ValueError):
            evaluate_prop(stats([1]*10),DAY,"PTS",line=float("nan"))
        a=stats([1,2,3,4,5,6,7,8])
        a.append(dict(a[0],value=100))
        cleaned=clean_player_series(a,DAY)
        self.assertEqual(len(cleaned),8)
        self.assertEqual(cleaned[0]["value"],1.)

    def test_plays_must_match_exact_espn_event(self):
        plays=[
            {"text":"Home scores 2","awayScore":9,"homeScore":12,
             "period":{"number":3},"clock":{"displayValue":"8:13"}},
            {"text":"Away 3-pointer","awayScore":12,"homeScore":12,
             "period":{"number":3},"clock":{"displayValue":"8:01"}},
            {"text":"Home layup","awayScore":12,"homeScore":14,
             "period":{"number":3},"clock":{"displayValue":"7:54"}},
        ]
        payload={"header":{"id":"401300001"},"plays":plays}
        self.assertEqual(parse_plays(payload,"401300002"),[])
        data=parse_plays(payload,"401300001")
        self.assertEqual(len(data),3)
        self.assertEqual(play_run(data)["home_points"],2)
        self.assertEqual(play_run(data)["away_points"],3)
        self.assertEqual(play_run(data)["lead"],"VISITANTE")
        payload["plays"].append({"text":"unverified","homeScore":400,"awayScore":1})
        self.assertEqual(len(parse_plays(payload,"401300001")),3)
        self.assertIsNone(play_run(data[:1]))

    def test_radar_is_bounded_not_a_hardcoded_bookmaker_ticket(self):
        def roster(team):
            return {"athletes":[
                {"id":str(10000+int(team)*10+i),"name":f"Player {team} {i}",
                 "team_id":str(team),"status":"Active","injuries":[]}
                for i in range(7)
            ]}
        def gamelog(player,day):
            entries=[]
            metadata={}
            for i in range(10):
                eid=str(int(player)*100+i)
                metadata[eid]={"gameDate":(day-timedelta(days=i+2)).isoformat()+"T02:00:00Z"}
                pts=32 if i<3 else 20
                entries.append({"eventId":eid,
                                "stats":["31","8-15","3-8","3-3","6","5",str(pts)]})
            return {"payload":{
                "labels":["MIN","FG","3PT","FT","REB","AST","PTS"],
                "events":metadata,"seasonTypes":[
                    {"id":"2","displayName":"Regular Season",
                     "categories":[{"events":entries}]}
                ]}}
        game={"sport":"NBA","event_id":"401300001","away_team_id":"7","home_team_id":"8"}
        scan=player_radar([game],DAY,roster_fetch=roster,gamelog_fetch=gamelog,
                          per_team=3,max_players=6)
        self.assertEqual(scan["players_checked"],6)
        self.assertTrue(scan["ideas"])
        self.assertTrue(all(row["stat"]=="PTS" for row in scan["ideas"]))
        self.assertTrue(all(row["direction"]=="SUBIENDO" for row in scan["ideas"]))
        self.assertFalse(scan["bookmaker_lines_used"])
        with self.assertRaises(ValueError):
            player_radar([game,game],DAY,roster_fetch=roster,gamelog_fetch=gamelog)
