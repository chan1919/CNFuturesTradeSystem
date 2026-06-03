import pytest

from src.strategy.bar import Bar
from src.strategy.indicator import IndicatorService, ema, macd, sma


def make_bar(instrument_id="rb2501", close_price=3500.0, high_price=3510.0):
    return Bar(
        instrument_id=instrument_id,
        timestamp=None,
        open_price=close_price,
        high_price=high_price,
        low_price=close_price,
        close_price=close_price,
        volume=10,
    )


class TestSma:
    def test_sma_returns_none_when_insufficient_values(self):
        assert sma([1.0, 2.0], period=3) is None

    def test_sma_uses_last_period_values(self):
        assert sma([1.0, 2.0, 3.0, 4.0], period=3) == 3.0

    def test_sma_rejects_invalid_period(self):
        with pytest.raises(ValueError, match="period"):
            sma([1.0, 2.0], period=0)


class TestEma:
    def test_ema_returns_none_when_insufficient_values(self):
        assert ema([1.0, 2.0], period=3) is None

    def test_ema_uses_sma_seed(self):
        assert ema([1.0, 2.0, 3.0, 4.0, 5.0], period=3) == pytest.approx(4.0)

    def test_ema_rejects_invalid_period(self):
        with pytest.raises(ValueError, match="period"):
            ema([1.0, 2.0], period=-1)


class TestMacd:
    def test_macd_returns_none_when_insufficient_values(self):
        assert macd([1.0, 2.0, 3.0], fast_period=2, slow_period=3, signal_period=2) is None

    def test_macd_returns_latest_values(self):
        result = macd([1.0, 2.0, 4.0, 8.0, 16.0, 32.0], fast_period=2, slow_period=3, signal_period=2)

        assert result is not None
        assert set(result) == {"macd", "signal", "histogram"}
        assert result["histogram"] == pytest.approx(result["macd"] - result["signal"])

    def test_macd_requires_fast_period_less_than_slow_period(self):
        with pytest.raises(ValueError, match="fast_period"):
            macd([1.0, 2.0, 3.0], fast_period=3, slow_period=2, signal_period=2)


class TestIndicatorService:
    def test_add_bar_and_latest_bar(self):
        service = IndicatorService(maxlen=10)
        bar = make_bar(close_price=3500.0)

        service.add_bar(bar)

        assert service.latest_bar("rb2501") is bar

    def test_closes_returns_close_prices(self):
        service = IndicatorService(maxlen=10)
        service.add_bar(make_bar(close_price=3500.0))
        service.add_bar(make_bar(close_price=3510.0))

        assert service.closes("rb2501") == [3500.0, 3510.0]

    def test_service_sma_uses_cached_bars(self):
        service = IndicatorService(maxlen=10)
        for price in (3500.0, 3510.0, 3520.0):
            service.add_bar(make_bar(close_price=price))

        assert service.sma("rb2501", period=2) == 3515.0

    def test_service_ema_uses_cached_bars(self):
        service = IndicatorService(maxlen=10)
        for price in (1.0, 2.0, 3.0, 4.0, 5.0):
            service.add_bar(make_bar(close_price=price))

        assert service.ema("rb2501", period=3) == pytest.approx(4.0)

    def test_service_macd_uses_cached_bars(self):
        service = IndicatorService(maxlen=10)
        for price in (1.0, 2.0, 4.0, 8.0, 16.0, 32.0):
            service.add_bar(make_bar(close_price=price))

        result = service.macd("rb2501", fast_period=2, slow_period=3, signal_period=2)

        assert result is not None
        assert result["histogram"] == pytest.approx(result["macd"] - result["signal"])

    def test_service_can_use_non_close_field(self):
        service = IndicatorService(maxlen=10)
        service.add_bar(make_bar(close_price=1.0, high_price=10.0))
        service.add_bar(make_bar(close_price=2.0, high_price=20.0))

        assert service.sma("rb2501", period=2, field="high_price") == 15.0

    def test_maxlen_is_applied_per_instrument(self):
        service = IndicatorService(maxlen=2)
        for price in (1.0, 2.0, 3.0):
            service.add_bar(make_bar(close_price=price))

        assert service.closes("rb2501") == [2.0, 3.0]

    def test_clear_removes_cached_bars(self):
        service = IndicatorService(maxlen=10)
        service.add_bar(make_bar("rb2501", close_price=1.0))
        service.add_bar(make_bar("m2609", close_price=2.0))

        service.clear("rb2501")

        assert service.closes("rb2501") == []
        assert service.closes("m2609") == [2.0]
