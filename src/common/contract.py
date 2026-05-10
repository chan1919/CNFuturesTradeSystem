from src.common.exchange import Exchange


def _split_instrument_id(instrument_id):
    alpha = ""
    digits = ""
    for ch in instrument_id:
        if ch.isdigit():
            digits += ch
        else:
            alpha += ch
    return alpha, digits


class Contract:

    def __init__(self, instrument_id: str, exchange: Exchange, product_id: str, year: int, month: int):
        self.instrument_id = instrument_id
        self.exchange = exchange
        self.product_id = product_id
        self.year = year
        self.month = month
        self.year_month = f"{year:02d}{month:02d}"

    @classmethod
    def from_ctp(cls, instrument_id: str, exchange: Exchange) -> "Contract":
        if exchange not in Exchange.__members__.values():
            raise ValueError(f"不支持的交易所: {exchange}")

        product_id, digits = _split_instrument_id(instrument_id)

        if len(digits) >= 4:
            year = int(digits[-4:-2])
            month = int(digits[-2:])
        elif len(digits) == 3:
            year = int("2" + digits[0])
            month = int(digits[1:3])
        else:
            raise ValueError(f"无法解析合约代码: {instrument_id}")

        return cls(
            instrument_id=instrument_id,
            exchange=exchange,
            product_id=product_id,
            year=year,
            month=month,
        )

    def __repr__(self):
        return f"<Contract {self.instrument_id} {self.exchange.value}>"

    def __str__(self):
        return self.instrument_id

    def __eq__(self, other):
        if not isinstance(other, Contract):
            return NotImplemented
        return self.instrument_id == other.instrument_id and self.exchange == other.exchange

    def __hash__(self):
        return hash((self.instrument_id, self.exchange))