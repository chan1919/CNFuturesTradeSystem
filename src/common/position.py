from dataclasses import dataclass

from src.common.contract import Contract


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


@dataclass
class Position:
    contract: Contract

    long_yd: int = 0
    long_today: int = 0
    long_avg_price: float = 0.0
    long_frozen: int = 0

    short_yd: int = 0
    short_today: int = 0
    short_avg_price: float = 0.0
    short_frozen: int = 0

    last_price: float = 0.0
    realized_pnl: float = 0.0

    @property
    def instrument_id(self) -> str:
        return self.contract.instrument_id

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

    @property
    def unrealized_pnl(self) -> float:
        long_pnl = (
            (self.last_price - self.long_avg_price)
            * self.contract.multiplier
            * self.long_volume
        )
        short_pnl = (
            (self.short_avg_price - self.last_price)
            * self.contract.multiplier
            * self.short_volume
        )
        return long_pnl + short_pnl

    def update_last_price(self, price: float):
        self.last_price = price

    def apply_trade(self, direction: str, offset: str, volume: int, price: float):
        if direction == "buy":
            if offset == "open":
                self.long_today += volume
                total = self.long_avg_price * (self.long_volume - volume)
                self.long_avg_price = (
                    (total + price * volume) / self.long_volume
                    if self.long_volume
                    else price
                )
            else:
                self.short_yd, self.short_today = _reduce_position(
                    self.short_yd, self.short_today, volume, offset
                )
                self.realized_pnl += (
                    (self.short_avg_price - price) * self.contract.multiplier * volume
                )
        elif direction == "sell":
            if offset == "open":
                self.short_today += volume
                total = self.short_avg_price * (self.short_volume - volume)
                self.short_avg_price = (
                    (total + price * volume) / self.short_volume
                    if self.short_volume
                    else price
                )
            else:
                self.long_yd, self.long_today = _reduce_position(
                    self.long_yd, self.long_today, volume, offset
                )
                self.realized_pnl += (
                    (price - self.long_avg_price) * self.contract.multiplier * volume
                )
