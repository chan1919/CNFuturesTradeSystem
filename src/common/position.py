from dataclasses import dataclass


@dataclass
class Position:
    """单合约持仓模型 — 多空分列（匹配 CTP 双向持仓）"""

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
