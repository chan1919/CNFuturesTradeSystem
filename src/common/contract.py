from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.common.exchange import Exchange
from src.common.commission import CommissionModel


def parse_year_month(instrument_id: str) -> tuple[int, int, str]:
    digits = "".join(ch for ch in instrument_id if ch.isdigit())
    nd = len(digits)
    if nd >= 4:
        year = int(digits[-4:-2])
        month = int(digits[-2:])
    elif nd == 3:
        year = int("2" + digits[0])
        month = int(digits[1:3])
    else:
        raise ValueError(f"cannot parse year/month from {instrument_id}")
    product_id = instrument_id[: -nd] if nd >= 4 else instrument_id[: -nd]
    return year, month, product_id


@dataclass(unsafe_hash=True)
class Contract:
    instrument_id: str
    exchange: Exchange
    product_id: str
    year: int
    month: int
    multiplier: int
    price_tick: Decimal
    commission: Optional[CommissionModel] = field(default=None, hash=False, compare=False)

    def __str__(self):
        return self.instrument_id