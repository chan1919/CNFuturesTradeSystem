from dataclasses import dataclass

from src.common.exchange import Exchange


@dataclass(unsafe_hash=True)
class Contract:
    instrument_id: str
    exchange: Exchange
    multiplier: int  # 合约乘数（如螺纹钢 10 吨/手，股指 300 元/点）
    tick_size: float  # 最小变动价位

    def __str__(self):
        return self.instrument_id