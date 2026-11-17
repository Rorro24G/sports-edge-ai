from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from src.content_feed import NewsError
feed={'checked_at_utc':'2026-11-17T18:00:00+00:00','articles':[{'headline':'Lakers availability update','published_utc':'2026-11-17T17:00:00+00:00','url':'https://www.espn.com/nba/story/_/id/123/news'}]}
with patch('src.news_ui.cached_news',return_value=feed):
    app=AppTest.from_string('from src.news_ui import render\nrender()').run()
    assert not app.exception
    assert 'Lakers availability update' in '\n'.join(x.value for x in app.markdown)
    app.text_input(key='news_search').set_value('unmatched').run()
    assert any('No hay titulares' in x.value for x in app.info)
with patch('src.news_ui.cached_news',side_effect=NewsError('No se pudieron actualizar las noticias.')):
    app=AppTest.from_string('from src.news_ui import render\nrender()').run()
    assert not app.exception and app.warning
report={'generated_at_utc':'2026-11-17T18:00:00+00:00','leagues':{'NBA':{'events':[{'partido':'Boston @ Miami','hora_cdmx':'22:00','estado':'PRE'}],'errors':[]}}}
with patch('src.parlay_ui.load_today_snapshot',return_value=None),patch('src.parlay_ui.cached_live_report',return_value=report) as fetch:
    app=AppTest.from_string('from src.parlay_ui import render\nrender()').run()
    assert not app.exception
    fetch.assert_called_once()
    assert len(app.dataframe)==1
    assert 'Boston @ Miami' in app.dataframe[0].value.to_string()
print('CONTENT_UI_OK')
