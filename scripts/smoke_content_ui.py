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
# The standalone view must fail clearly if its ESPN analysis dependency is absent.
# The fully wired app flow is covered by scripts/smoke_parlay_ui.py.
app=AppTest.from_string('from src.parlay_ui import render\nrender()').run()
assert not app.exception
assert any('analizador ESPN' in str(x.value) for x in app.warning)
print('CONTENT_UI_OK')
