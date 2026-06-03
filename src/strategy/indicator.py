from src.strategy.bar import Bar, BarCache


def sma(values: list[float], period: int) -> float | None:
    _validate_period(period)
    if len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def ema(values: list[float], period: int) -> float | None:
    _validate_period(period)
    if len(values) < period:
        return None

    alpha = 2 / (period + 1)
    current = sum(values[:period]) / period
    for value in values[period:]:
        current = value * alpha + current * (1 - alpha)
    return current


def macd(
    values: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> dict[str, float] | None:
    _validate_period(fast_period, "fast_period")
    _validate_period(slow_period, "slow_period")
    _validate_period(signal_period, "signal_period")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")

    macd_line = _ema_series(values, fast_period, start_index=slow_period - 1)
    slow_line = _ema_series(values, slow_period)
    if slow_line is None or macd_line is None:
        return None

    diffs = [fast - slow for fast, slow in zip(macd_line, slow_line)]
    signal = ema(diffs, signal_period)
    if signal is None:
        return None


    latest_macd = diffs[-1]
    return {
        "macd": latest_macd,
        "signal": signal,
        "histogram": latest_macd - signal,
    }


class IndicatorService:
    def __init__(self, maxlen: int = 1000):
        self._cache = BarCache(maxlen=maxlen)

    def add_bar(self, bar: Bar):
        self._cache.add(bar)

    def latest_bar(self, instrument_id: str) -> Bar | None:
        return self._cache.latest(instrument_id)

    def bars(self, instrument_id: str, count: int | None = None) -> list[Bar]:
        return self._cache.get(instrument_id, count=count)

    def values(self, instrument_id: str, field: str = "close_price", count: int | None = None) -> list[float]:
        result = []
        for bar in self.bars(instrument_id, count=count):
            value = getattr(bar, field)
            result.append(float(value))
        return result

    def closes(self, instrument_id: str, count: int | None = None) -> list[float]:
        return self.values(instrument_id, field="close_price", count=count)

    def sma(self, instrument_id: str, period: int, field: str = "close_price") -> float | None:
        return sma(self.values(instrument_id, field=field), period)

    def ema(self, instrument_id: str, period: int, field: str = "close_price") -> float | None:
        return ema(self.values(instrument_id, field=field), period)

    def macd(
        self,
        instrument_id: str,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        field: str = "close_price",
    ) -> dict[str, float] | None:
        return macd(
            self.values(instrument_id, field=field),
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
        )

    def clear(self, instrument_id: str | None = None):
        self._cache.clear(instrument_id)


def _validate_period(period: int, name: str = "period"):
    if period <= 0:
        raise ValueError(f"{name} must be positive")


def _ema_series(values: list[float], period: int, start_index: int | None = None) -> list[float] | None:
    if len(values) < period:
        return None

    alpha = 2 / (period + 1)
    current = sum(values[:period]) / period
    series = [current]
    for value in values[period:]:
        current = value * alpha + current * (1 - alpha)
        series.append(current)

    if start_index is None:
        return series

    offset = start_index - period + 1
    if offset < 0:
        return None
    return series[offset:]
