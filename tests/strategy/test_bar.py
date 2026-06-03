from datetime import datetime

from src.strategy.bar import Bar, BarBuilder, BarCache


def make_tick(
    instrument_id="rb2501",
    last_price=3500.0,
    volume=100,
    update_time="09:00:01",
    action_day="20260428",
    trading_day="20260428",
    open_interest=1000.0,
):
    return {
        "instrument_id": instrument_id,
        "last_price": last_price,
        "volume": volume,
        "update_time": update_time,
        "update_millisec": 500,
        "action_day": action_day,
        "trading_day": trading_day,
        "open_interest": open_interest,
    }


def make_bar(instrument_id="rb2501", minute=0, close_price=3500.0):
    return Bar(
        instrument_id=instrument_id,
        timestamp=datetime(2026, 4, 28, 9, minute),
        open_price=3500.0,
        high_price=3510.0,
        low_price=3490.0,
        close_price=close_price,
        volume=10,
        open_interest=1000.0,
        trading_day="20260428",
        action_day="20260428",
    )


class TestBar:
    def test_bar_stores_ohlcv_fields(self):
        bar = make_bar(close_price=3505.0)

        assert bar.instrument_id == "rb2501"
        assert bar.timestamp == datetime(2026, 4, 28, 9, 0)
        assert bar.open_price == 3500.0
        assert bar.high_price == 3510.0
        assert bar.low_price == 3490.0
        assert bar.close_price == 3505.0
        assert bar.volume == 10
        assert bar.open_interest == 1000.0
        assert bar.trading_day == "20260428"
        assert bar.action_day == "20260428"


class TestBarBuilder:
    def test_first_tick_starts_current_bar(self):
        builder = BarBuilder()

        completed = builder.update_tick(make_tick())

        assert completed is None
        bar = builder.current_bar("rb2501")
        assert bar.timestamp == datetime(2026, 4, 28, 9, 0)
        assert bar.open_price == 3500.0
        assert bar.high_price == 3500.0
        assert bar.low_price == 3500.0
        assert bar.close_price == 3500.0
        assert bar.volume == 0

    def test_same_minute_updates_ohlcv(self):
        builder = BarBuilder()

        builder.update_tick(make_tick(last_price=3500.0, volume=100, update_time="09:00:01"))
        builder.update_tick(make_tick(last_price=3510.0, volume=105, update_time="09:00:20"))
        builder.update_tick(make_tick(last_price=3490.0, volume=110, update_time="09:00:59"))

        bar = builder.current_bar("rb2501")
        assert bar.open_price == 3500.0
        assert bar.high_price == 3510.0
        assert bar.low_price == 3490.0
        assert bar.close_price == 3490.0
        assert bar.volume == 10

    def test_new_minute_returns_completed_bar_and_starts_next(self):
        builder = BarBuilder()

        builder.update_tick(make_tick(last_price=3500.0, volume=100, update_time="09:00:01"))
        builder.update_tick(make_tick(last_price=3510.0, volume=105, update_time="09:00:20"))
        completed = builder.update_tick(make_tick(last_price=3505.0, volume=109, update_time="09:01:00"))

        assert completed.instrument_id == "rb2501"
        assert completed.timestamp == datetime(2026, 4, 28, 9, 0)
        assert completed.close_price == 3510.0
        assert completed.volume == 5

        current = builder.current_bar("rb2501")
        assert current.timestamp == datetime(2026, 4, 28, 9, 1)
        assert current.open_price == 3505.0
        assert current.close_price == 3505.0
        assert current.volume == 4

    def test_tracks_multiple_instruments_independently(self):
        builder = BarBuilder()

        builder.update_tick(make_tick("rb2501", 3500.0, 100, "09:00:01"))
        builder.update_tick(make_tick("m2609", 2800.0, 50, "09:00:01"))
        completed = builder.update_tick(make_tick("rb2501", 3505.0, 103, "09:01:01"))

        assert completed.instrument_id == "rb2501"
        assert builder.current_bar("rb2501").timestamp == datetime(2026, 4, 28, 9, 1)
        assert builder.current_bar("m2609").timestamp == datetime(2026, 4, 28, 9, 0)

    def test_ignores_tick_without_required_fields(self):
        builder = BarBuilder()

        assert builder.update_tick({"instrument_id": "rb2501"}) is None
        assert builder.current_bar("rb2501") is None

    def test_ignores_out_of_order_tick(self):
        builder = BarBuilder()

        builder.update_tick(make_tick(last_price=3500.0, volume=100, update_time="09:01:01"))
        completed = builder.update_tick(make_tick(last_price=3490.0, volume=101, update_time="09:00:59"))

        assert completed is None
        assert builder.current_bar("rb2501").timestamp == datetime(2026, 4, 28, 9, 1)
        assert builder.current_bar("rb2501").close_price == 3500.0

    def test_flush_returns_and_removes_current_bar(self):
        builder = BarBuilder()
        builder.update_tick(make_tick())

        bar = builder.flush("rb2501")

        assert bar.instrument_id == "rb2501"
        assert builder.current_bar("rb2501") is None


class TestBarCache:
    def test_add_and_latest(self):
        cache = BarCache(maxlen=10)
        bar = make_bar()

        cache.add(bar)

        assert cache.latest("rb2501") is bar

    def test_keeps_maxlen_per_instrument(self):
        cache = BarCache(maxlen=2)
        first = make_bar(minute=0, close_price=3500.0)
        second = make_bar(minute=1, close_price=3501.0)
        third = make_bar(minute=2, close_price=3502.0)

        cache.add(first)
        cache.add(second)
        cache.add(third)

        assert cache.get("rb2501") == [second, third]

    def test_get_count_returns_tail_copy(self):
        cache = BarCache(maxlen=10)
        first = make_bar(minute=0, close_price=3500.0)
        second = make_bar(minute=1, close_price=3501.0)
        third = make_bar(minute=2, close_price=3502.0)
        for bar in (first, second, third):
            cache.add(bar)

        result = cache.get("rb2501", count=2)
        result.clear()

        assert cache.get("rb2501", count=2) == [second, third]

    def test_separates_instruments(self):
        cache = BarCache(maxlen=10)
        rb = make_bar("rb2501")
        m = make_bar("m2609")

        cache.add(rb)
        cache.add(m)

        assert cache.get("rb2501") == [rb]
        assert cache.get("m2609") == [m]

    def test_clear_one_instrument(self):
        cache = BarCache(maxlen=10)
        cache.add(make_bar("rb2501"))
        cache.add(make_bar("m2609"))

        cache.clear("rb2501")

        assert cache.get("rb2501") == []
        assert len(cache.get("m2609")) == 1
