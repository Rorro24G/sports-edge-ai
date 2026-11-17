"""Portal isolates landing from feeds and routes into real sections."""
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

with patch('src.content_feed.fetch_news', side_effect=AssertionError('Landing must not load news')), patch('src.content_feed.live_parlay_report', side_effect=AssertionError('Landing must not load parlays')):
    app = AppTest.from_file('../app.py').run()
    assert not app.exception
    assert len([b for b in app.button if str(b.key).startswith('direct_')]) == 6
    assert not app.text_input
    app.button(key='direct_historial').click().run()
    assert not app.exception
    assert app.session_state['brain_section'] == 'historial'
    app.button(key='back_to_brain').click().run()
    assert not app.exception
    assert app.session_state['brain_section'] is None
    assert app.session_state['brain_entered'] is True
with patch('src.brain_portal.portal', return_value={'page':'asistente','nonce':1}):
    app = AppTest.from_file('../app.py').run()
    assert not app.exception
    assert not app.text_input, 'Only the six public nodes can route from component events'
with patch('src.brain_portal.portal', return_value={'page':'historial','nonce':2}):
    app = AppTest.from_file('../app.py').run()
    assert not app.exception
    assert app.session_state['brain_section'] == 'historial'
print('BRAIN_PORTAL_ROUTING_OK')
