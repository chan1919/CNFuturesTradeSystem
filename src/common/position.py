from dataclasses import dataclass


@dataclass
class Position:
    instrument_id: str

    long_yd: int = 0
    long_today: int = 0
    long_avg_price: float = 0.0
    long_frozen: int = 0

    short_yd: int = 0
    short_today: int = 0
    short_avg_price: float = 0.0
    short_frozen: int = 0

    last_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    @property
    def long_volume(self) -> int:
        return self.long_yd + self.long_today

    @property
    def short_volume(self) -> int:
        return self.short_yd + self.short_today

    @property
    def net(self) -> int:
        return self.long_volume - self.short_volume

    @property
    def is_flat(self) -> bool:
        return self.long_volume == 0 and self.short_volume == 0

    @property
    def is_long_only(self) -> bool:
        return self.long_volume > 0 and self.short_volume == 0

    @property
    def is_short_only(self) -> bool:
        return self.short_volume > 0 and self.long_volume == 0

    def update_from_ctp(self, posi_direction: str, yd: int = 0, today: int = 0,
                        frozen: int = 0, avg_price: float = 0.0):
        if posi_direction == "2":
            self.long_yd = yd
            self.long_today = today
            self.long_frozen = frozen
            self.long_avg_price = avg_price if avg_price else self.long_avg_price
        elif posi_direction == "3":
            self.short_yd = yd
            self.short_today = today
            self.short_frozen = frozen
            self.short_avg_price = avg_price if avg_price else self.short_avg_price

    def apply_trade(self, direction: str, offset: str, volume: int, price: float):
        direction = _normalize_direction(direction)
        offset = _normalize_offset(offset)

        if direction == "buy":
            if offset == "open":
                self.long_today += volume
                total = self.long_avg_price * (self.long_volume - volume)
                self.long_avg_price = (total + price * volume) / self.long_volume if self.long_volume else price
            else:
                self.short_yd, self.short_today = _reduce_position(
                    self.short_yd, self.short_today, volume, offset
                )
        elif direction == "sell":
            if offset == "open":
                self.short_today += volume
                total = self.short_avg_price * (self.short_volume - volume)
                self.short_avg_price = (total + price * volume) / self.short_volume if self.short_volume else price
            else:
                self.long_yd, self.long_today = _reduce_position(
                    self.long_yd, self.long_today, volume, offset
                )


def _normalize_direction(direction: str) -> str:
    return {
        "0": "buy",
        "1": "sell",
    }.get(direction, direction)


def _normalize_offset(offset: str) -> str:
    return {
        "0": "open",
        "1": "close",
        "3": "close_today",
        "4": "close_yesterday",
    }.get(offset, offset)


def _reduce_position(yd: int, today: int, volume: int, offset: str) -> tuple[int, int]:
    if volume <= 0:
        return yd, today

    if offset == "close_today":
        return yd, max(0, today - volume)

    if offset == "close_yesterday":
        return max(0, yd - volume), today

    yd_used = min(yd, volume)
    yd -= yd_used
    today -= min(today, volume - yd_used)
    return yd, today
