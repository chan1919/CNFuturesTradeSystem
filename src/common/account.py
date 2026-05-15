from src.common.position import Position
from src.common.contract import Contract


class Account:
    """账户模型 — 资金 + 仓位

    资金字段通过 update_from_query() 从 CTP Query 全量更新。
    仓位字段通过 apply_trade() / update_from_ctp() 更新。
    """

    def __init__(self):
        self._balance: float = 0.0
        self._available: float = 0.0
        self._curr_margin: float = 0.0
        self._frozen_margin: float = 0.0
        self._frozen_cash: float = 0.0
        self._position_profit: float = 0.0
        self._commission: float = 0.0
        self._pre_balance: float = 0.0

        self._positions: dict[str, Position] = {}

    # ── 资金属性（只读） ──

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def available(self) -> float:
        return self._available

    @property
    def curr_margin(self) -> float:
        return self._curr_margin

    @property
    def frozen_margin(self) -> float:
        return self._frozen_margin

    @property
    def frozen_cash(self) -> float:
        return self._frozen_cash

    @property
    def position_profit(self) -> float:
        return self._position_profit

    @property
    def commission(self) -> float:
        return self._commission

    @property
    def pre_balance(self) -> float:
        return self._pre_balance

    # ── 资金更新 ──

    def update_from_query(self, data: dict):
        """从 OnRspQryTradingAccount 更新资金字段"""
        self._balance = data.get("balance", self._balance)
        self._available = data.get("available", self._available)
        self._curr_margin = data.get("curr_margin", self._curr_margin)
        self._frozen_margin = data.get("frozen_margin", self._frozen_margin)
        self._frozen_cash = data.get("frozen_cash", self._frozen_cash)
        self._position_profit = data.get("position_profit", self._position_profit)
        self._commission = data.get("commission", self._commission)
        self._pre_balance = data.get("pre_balance", self._pre_balance)

    # ── 仓位管理 ──

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