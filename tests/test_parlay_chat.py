"""Parlay chat: tests offline, no real API credentials or network."""
import io
import json
from unittest import TestCase
from unittest.mock import patch

from src.parlay_chat import ParlayChatError, ask_about_parlay


class MockResponse:
    def __init__(self, payload):
        self.content = io.BytesIO(json.dumps(payload).encode("utf-8"))
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n):
        return self.content.read(n)


class ParlayChatTests(TestCase):
    def test_discussion_without_action_tools(self):
        captured = {}
        def fake_request(req, timeout=0):
            data = json.loads(req.data)
            captured.update(data)
            return MockResponse({
                "output": [{
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Revisa las cuotas y su correlación."}],
                }],
            })
        with patch("src.parlay_chat.urlopen", side_effect=fake_request):
            answer = ask_about_parlay([{"role": "user", "content": "¿Es buena esta combinada?"}],
                                      api_key="test-only-key", model="test-model")
        self.assertIn("correlación", answer)
        self.assertEqual(captured["store"], False)
        self.assertNotIn("tools", captured)
        self.assertEqual(captured["model"], "test-model")

    def test_fails_closed_without_config(self):
        with self.assertRaises(ParlayChatError):
            ask_about_parlay([{"role": "user", "content": "hola"}],
                             api_key="", model="test-model")
        with self.assertRaises(ParlayChatError):
            ask_about_parlay([{"role": "assistant", "content": "hola"}],
                             api_key="valid-key", model="test-model")

    def test_empty_response_does_not_fake_answer(self):
        with patch("src.parlay_chat.urlopen", return_value=MockResponse({"output": []})):
            with self.assertRaises(ParlayChatError):
                ask_about_parlay([{"role": "user", "content": "hola"}],
                                 api_key="test-key", model="test-model")
