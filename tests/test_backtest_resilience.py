"""ESPN source instability must not be masked by fabricated observations."""
from unittest import TestCase
from unittest.mock import patch

from src.live_board import CalendarSourceError
from scripts.backtest_seai import _scoreboard_with_retries
from datetime import date


class BacktestResilienceTests(TestCase):
    @patch("scripts.backtest_seai.sleep")
    @patch("scripts.backtest_seai.fetch_scoreboard")
    def test_transient_scoreboard_error_retries_one_date(self, read, nap):
        payload = {"games": [{"event_id": "1"}]}
        read.side_effect = [CalendarSourceError("ESPN temporal"), payload]
        result = _scoreboard_with_retries("NBA", date(2025, 11, 11))
        self.assertEqual(result, payload)
        self.assertEqual(read.call_count, 2)
        nap.assert_called_once()

    @patch("scripts.backtest_seai.sleep")
    @patch("scripts.backtest_seai.fetch_scoreboard")
    def test_persistent_failure_is_never_replaced_by_empty_fake_data(self, read, nap):
        read.side_effect = CalendarSourceError("ESPN no disponible")
        with self.assertRaises(CalendarSourceError):
            _scoreboard_with_retries("NBA", date(2025, 11, 11))
        self.assertEqual(read.call_count, 3)
        self.assertEqual(nap.call_count, 2)
