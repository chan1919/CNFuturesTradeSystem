from abc import ABC, abstractmethod

from src.common.position import Position


class StrategyStatus:
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class BaseStrategy(ABC):
    def __init__(self, name: str, runtime=None):
        self.name = name
        self.tags: set[str] = set()
        self.status = StrategyStatus.STOPPED
        self.runtime = runtime
        self.contracts: dict[str, "Contract"] = {}
        self.positions: dict[str, Position] = {}
        self.latest_ticks: dict[str, dict] = {}
        self.orders: dict[str, dict] = {}
        self.trades: dict[str, dict] = {}
        self._enabled: bool = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def subscribed_instrument_ids(self) -> set[str]:
        return set(self.contracts.keys())

    def add_contract(self, contract: "Contract"):
        self.contracts[contract.instrument_id] = contract
        self.positions.setdefault(contract.instrument_id, Position(instrument_id=contract.instrument_id))
        self.latest_ticks.setdefault(contract.instrument_id, {})

    def has_all_ticks(self, *instrument_ids: str) -> bool:
        return all(
            self.latest_ticks.get(iid, {}).get("last_price") is not None
            for iid in instrument_ids
        )

    def price(self, instrument_id: str) -> float | None:
        tick = self.latest_ticks.get(instrument_id, {})
        return tick.get("last_price")

    # ── 下单辅助 ──

    def buy(self, instrument_id: str, volume: int, price: float | None = None):
        if self.runtime:
            self.runtime.send_order_for_strategy(self, instrument_id, "buy", "open", price or 0, volume)

    def sell(self, instrument_id: str, volume: int, price: float | None = None):
        if self.runtime:
            self.runtime.send_order_for_strategy(self, instrument_id, "sell", "open", price or 0, volume)

    def close_long(self, instrument_id: str, volume: int, price: float | None = None):
        if self.runtime:
            self.runtime.send_order_for_strategy(self, instrument_id, "sell", "close", price or 0, volume)

    def close_short(self, instrument_id: str, volume: int, price: float | None = None):
        if self.runtime:
            self.runtime.send_order_for_strategy(self, instrument_id, "buy", "close", price or 0, volume)

    # ── 生命周期 ──

    @abstractmethod
    def on_init(self):
        ...

    def on_start(self):
        pass

    def on_stop(self):
        self._enabled = False
        self.status = StrategyStatus.STOPPED

    def on_tick(self, tick: dict):
        pass

    def on_order(self, order: dict):
        pass

    def on_trade(self, trade: dict):
        pass

    def on_account(self, account: dict):
        pass