from datetime import date, datetime, timezone
from unittest import TestCase
from src.content_feed import normalize_news, live_parlay_report, NewsError
from src.parlay_research import build_reference_parlays
NOW = datetime(2026, 11, 17, 18, tzinfo=timezone.utc)
def article(**kw):
    row = {'headline':'Availability update','published':'2026-11-17T16:00:00Z','links':{'web':{'href':'https://www.espn.com/nba/story/_/id/123/news'}}}
    return dict(row, **kw)
class ContentTests(TestCase):
    def test_dates_and_duplicates(self):
        rows=[article(),article(),article(published='2026-11-12T16:00:00Z'),article(published='2026-11-18T16:00:00Z'),article(published='bad'),article(published='2026-11-17T16:00:00')]
        self.assertEqual(len(normalize_news({'articles':rows},now=NOW)),1)
    def test_bad_links(self):
        rows=[article(links={'web':{'href':u}}) for u in ['https://espn.com.evil.test','javascript:alert(1)']]
        self.assertEqual(normalize_news({'articles':rows},now=NOW),[])
    def test_invalid_is_not_empty(self):
        self.assertEqual(normalize_news({'articles':[]},now=NOW),[])
        with self.assertRaises(NewsError):normalize_news({},now=NOW)
    def test_live_without_snapshot_and_started_game(self):
        def picks(league,day):
            return {'events':[{'liga':league,'partido':'Boston @ Miami','fecha_cdmx':day.isoformat(),'hora_cdmx':'22:00','fuente':'https://www.covers.com/picks/nba','proyeccion_visitante':100,'proyeccion_local':110,'momio_visitante':'+110','momio_local':'-120'}] if league=='NBA' else []}
        def board(league,day):
            return {'games':[{'sport':league,'away':'Boston','home':'Miami','local_time':'22:00','status':'PRE','event_id':league+'123'}]}
        report=live_parlay_report(NOW.date(),covers_fetch=picks,board_fetch=board)
        self.assertEqual(len(build_reference_parlays(report,legs_per_parlay=1,now=NOW)),1)
        report['leagues']['NBA']['events'][0]['espn']['estado']='POST'
        self.assertEqual(build_reference_parlays(report,legs_per_parlay=1,now=NOW),[])
    def test_source_failure_keeps_calendar(self):
        def failed(*args):raise OSError('offline')
        def board(league,day):
            return {'games':[{'sport':league,'away':'Boston','home':'Miami','local_time':'22:00','status':'PRE','event_id':league+'123'}]}
        report=live_parlay_report(NOW.date(),covers_fetch=failed,board_fetch=board)
        self.assertEqual(len(report['leagues']['NBA']['events']),1)
        self.assertEqual(report['leagues']['NBA']['coverage']['covers'],'error')
        self.assertEqual(build_reference_parlays(report,now=NOW),[])
