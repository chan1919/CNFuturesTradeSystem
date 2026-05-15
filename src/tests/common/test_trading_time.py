from datetime import datetime

from src.common.trading_time import in_connection_window, session_label


class TestOutsideWindow:
    def test_monday_early_morning_is_excluded(self):
        now = datetime(2026, 4, 27, 1, 0, 0)
        assert in_connection_window(now) is False
        assert session_label(now) is None

    def test_sunday_night_is_excluded(self):
        now = datetime(2026, 4, 26, 22, 0, 0)
        assert in_connection_window(now) is False
        assert session_label(now) is None

    def test_before_day_session(self):
        now = datetime(2026, 4, 28, 8, 0, 0)
        assert in_connection_window(now) is False
        assert session_label(now) is None

    def test_after_day_before_night(self):
        now = datetime(2026, 4, 28, 15, 30, 0)
        assert in_connection_window(now) is False
        assert session_label(now) is None

    def test_weekend_after_night_extension(self):
        now = datetime(2026, 5, 2, 10, 0, 0)
        assert in_connection_window(now) is False
        assert session_label(now) is None


class TestDaySession:
    def test_weekday_morning(self):
        now = datetime(2026, 4, 28, 9, 0, 0)
        assert in_connection_window(now) is True
        assert session_label(now) == "day"

    def test_weekday_afternoon(self):
        now = datetime(2026, 4, 29, 14, 30, 0)
        assert in_connection_window(now) is True
        assert session_label(now) == "day"

    def test_friday_day_session(self):
        now = datetime(2026, 5, 1, 10, 0, 0)
        assert in_connection_window(now) is True
        assert session_label(now) == "day"


class TestNightSession:
    def test_monday_night_session(self):
        now = datetime(2026, 4, 27, 22, 0, 0)
        assert in_connection_window(now) is True
        assert session_label(now) == "night"

    def test_tuesday_night_tail(self):
        now = datetime(2026, 4, 28, 1, 0, 0)
        assert in_connection_window(now) is True
        assert session_label(now) == "night"

    def test_wednesday_night_to_thursday_morning(self):
        night = datetime(2026, 4, 29, 22, 0, 0)
        tail = datetime(2026, 4, 30, 2, 0, 0)
        assert in_connection_window(night) is True
        assert session_label(night) == "night"
        assert in_connection_window(tail) is True
        assert session_label(tail) == "night"

    def test_friday_night_extends_to_saturday_morning(self):
        friday_night = datetime(2026, 5, 1, 22, 0, 0)
        saturday_tail = datetime(2026, 5, 2, 2, 0, 0)
        assert in_connection_window(friday_night) is True
        assert session_label(friday_night) == "night"
        assert in_connection_window(saturday_tail) is True
        assert session_label(saturday_tail) == "night"
