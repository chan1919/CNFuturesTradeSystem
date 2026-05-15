from src.common.position import Position
from src.common.contract import Contract


class Account:
    def __init__(self):
        self._positions: dict[str, Position] = {}

    @property
    def positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def get_position(self, instrument_id: str) -> Position | None:
        return self._positions.get(instrument_id)

    def get_all_positions(self) -> dict[str, Position]:
        return {iid: p for iid, p in self._positions.items() if not p.is_flat}

    def get_or_create(self, contract: Contract) -> Position:
        iid = contract.instrument_id
        if iid not in self._positions:
            self._positions[iid] = Position(contract=contract)
        return self._positions[iid]

    def apply_trade(self, contract: Contract, direction: str, offset: str, volume: int, price: float):
        pos = self.get_or_create(contract)
        pos.apply_trade(direction, offset, volume, price)

    def update_from_ctp(self, instrument_id: str, contract: Contract | None,
                        direction: str, yd: int = 0, today: int = 0,
                        frozen: int = 0, avg_price: float = 0.0):
        pos = self._positions.get(instrument_id)
        if pos is None:
            if contract is None:
                return
            pos = Position(contract=contract)
            self._positions[instrument_id] = pos

        if direction == "long":
            pos.long_yd = yd
            pos.long_today = today
            pos.long_frozen = frozen
            pos.long_avg_price = avg_price if avg_price else pos.long_avg_price
        elif direction == "short":
            pos.short_yd = yd
            pos.short_today = today
            pos.short_frozen = frozen
            pos.short_avg_price = avg_price if avg_price else pos.short_avg_price