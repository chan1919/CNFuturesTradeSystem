from dataclasses import dataclass
from decimal import Decimal

from src.common.exchange import Exchange


@dataclass(unsafe_hash=True)
class Contract:
    instrument_id: str
    exchange: Exchange
    product_id: str
    multiplier: int
    price_tick: Decimal

    def __str__(self):
        return self.instrument_id