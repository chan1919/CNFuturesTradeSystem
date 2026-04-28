from datetime import datetime

from trader.common.trading_time import in_connection_window, session_label


class TestTradingTime:
    def test_monday_early_morning_is_not_connection_window(self):
        now = datetime(2026, 4, 27, 1, 0, 0)
        assert in_connection_window(now) is False
        assert session_label(now) is None

    def test_weekday_day_session_is_connection_window(self):
        now = datetime(2026, 4, 28, 9, 0, 0)
        assert in_connection_window(now) is True
        assert session_label(now) == "day"

    def test_weekday_night_session_is_connection_window(self):
        now = datetime(2026, 4, 28, 21, 0, 0)
        assert in_connection_window(now) is True
        assert session_label(now) == "night"

    def test_friday_night_session_extends_to_saturday_morning(self):
        friday_night = datetime(2026, 5, 1, 21, 0, 0)
        saturday_early = datetime(2026, 5, 2, 2, 30, 0)
        assert in_connection_window(friday_night) is True
        assert session_label(friday_night) == "night"
        assert in_connection_window(saturday_early) is True
        assert session_label(saturday_early) == "night"

    def test_weekend_outside_night_extension_is_not_connection_window(self):
        now = datetime(2026, 5, 2, 10, 0, 0)
        assert in_connection_window(now) is False
        assert session_label(now) is None
