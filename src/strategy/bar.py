from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Bar:
    instrument_id: str
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    open_interest: float = 0.0
    trading_day: str = ""
    action_day: str = ""


class BarBuilder:
    """Builds 1-minute OHLCV bars from CTP depth market ticks."""

    def __init__(self):
        self._bars: dict[str, Bar] = {}
        self._last_volume: dict[str, int] = {}
        self._last_tick_time: dict[str, datetime] = {}

    def update_tick(self, tick: dict) -> Bar | None:
        instrument_id = tick.get("instrument_id")
        price = tick.get("last_price")
        tick_time = self._parse_tick_time(tick)
        if not instrument_id or price is None or tick_time is None:
            return None

        last_tick_time = self._last_tick_time.get(instrument_id)
        if last_tick_time is not None and tick_time < last_tick_time:
            return None

        current_volume = self._safe_int(tick.get("volume", 0))
        previous_volume = self._last_volume.get(instrument_id)
        volume_delta = 0 if previous_volume is None else max(0, current_volume - previous_volume)
        self._last_volume[instrument_id] = current_volume
        self._last_tick_time[instrument_id] = tick_time

        minute = tick_time.replace(second=0, microsecond=0)
        current = self._bars.get(instrument_id)
        if current is None:
            self._bars[instrument_id] = self._new_bar(tick, minute, float(price), volume=0)
            return None

        if minute == current.timestamp:
            self._update_bar(current, tick, float(price), volume_delta)
            return None

        completed = current
        self._bars[instrument_id] = self._new_bar(tick, minute, float(price), volume_delta)
        return completed

    def current_bar(self, instrument_id: str) -> Bar | None:
        return self._bars.get(instrument_id)

    def flush(self, instrument_id: str) -> Bar | None:
        self._last_volume.pop(instrument_id, None)
        self._last_tick_time.pop(instrument_id, None)
        return self._bars.pop(instrument_id, None)

    def _new_bar(self, tick: dict, minute: datetime, price: float, volume: int) -> Bar:
        return Bar(
            instrument_id=tick["instrument_id"],
            timestamp=minute,
            open_price=price,
            high_price=price,
            low_price=price,
            close_price=price,
            volume=volume,
            open_interest=float(tick.get("open_interest", 0) or 0),
            trading_day=tick.get("trading_day", "") or "",
            action_day=tick.get("action_day", "") or "",
        )

    def _update_bar(self, bar: Bar, tick: dict, price: float, volume_delta: int):
        bar.high_price = max(bar.high_price, price)
        bar.low_price = min(bar.low_price, price)
        bar.close_price = price
        bar.volume += volume_delta
        bar.open_interest = float(tick.get("open_interest", bar.open_interest) or 0)
        bar.trading_day = tick.get("trading_day", bar.trading_day) or bar.trading_day
        bar.action_day = tick.get("action_day", bar.action_day) or bar.action_day

    def _parse_tick_time(self, tick: dict) -> datetime | None:
        day = tick.get("action_day") or tick.get("trading_day")
        update_time = tick.get("update_time")
        if not day or not update_time:
            return None
        try:
            return datetime.strptime(f"{day} {update_time}", "%Y%m%d %H:%M:%S")
        except ValueError:
            return None

    def _safe_int(self, value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


class BarCache:
    def __init__(self, maxlen: int = 1000):
        if maxlen <= 0:
            raise ValueError("maxlen must be positive")
        self._bars = defaultdict(lambda: deque(maxlen=maxlen))

    def add(self, bar: Bar):
        self._bars[bar.instrument_id].append(bar)

    def latest(self, instrument_id: str) -> Bar | None:
        bars = self._bars.get(instrument_id)
        if not bars:
            return None
        return bars[-1]

    def get(self, instrument_id: str, count: int | None = None) -> list[Bar]:
        bars = list(self._bars.get(instrument_id, []))
        if count is None:
            return bars
        if count <= 0:
            return []
        return bars[-count:]

    def clear(self, instrument_id: str | None = None):
        if instrument_id is None:
            self._bars.clear()
            return
        self._bars.pop(instrument_id, None)
