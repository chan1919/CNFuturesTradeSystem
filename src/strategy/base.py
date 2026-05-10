from abc import ABC, abstractmethod
from src.strategy.unit import AbstractUnit, SyntheticUnit
from src.common.position import Position


class StrategyStatus:
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class BaseStrategy(ABC):
    def __init__(self, name: str, engine=None):
        self.name = name
        self.status = StrategyStatus.STOPPED
        self.engine = engine
        self.units: dict[str, AbstractUnit] = {}
        self._last_account: dict = {}

    # ── 单元管理 ──

    def add_unit(self, unit: AbstractUnit):
        self.units[unit.instrument_id] = unit

    def remove_unit(self, instrument_id: str):
        unit = self.units.pop(instrument_id, None)
        if unit:
            unit.disable()

    def get_unit(self, instrument_id: str) -> AbstractUnit | None:
        return self.units.get(instrument_id)

    def list_unit_ids(self) -> list[str]:
        return list(self.units.keys())

    def list_synthetic_units(self) -> list[SyntheticUnit]:
        return [u for u in self.units.values() if isinstance(u, SyntheticUnit)]

    # ── 委托操作 ──

    def enable(self, instrument_id: str):
        u = self.get_unit(instrument_id)
        if u:
            u.enable()

    def disable(self, instrument_id: str):
        u = self.get_unit(instrument_id)
        if u:
            u.disable()

    def update_params(self, instrument_id: str, params: dict):
        u = self.get_unit(instrument_id)
        if u:
            u.update_params(params)

    def restart(self, instrument_id: str):
        u = self.get_unit(instrument_id)
        if u:
            u.restart()

    def clear_position(self, instrument_id: str):
        u = self.get_unit(instrument_id)
        if u:
            u.clear_position()

    # ── 聚合查询 ──

    def get_all_positions(self) -> list[Position]:
        return [u.position for u in self.units.values()]

    def get_positions_for(self, product_id: str) -> list[Position]:
        return [u.position for u in self.units.values()
                if u.contract is not None and u.contract.product_id == product_id]

    # ── 生命周期 ──

    @abstractmethod
    def on_init(self):
        ...

    def on_start(self):
        for unit in self.units.values():
            unit.enable()

    def on_stop(self):
        for unit in self.units.values():
            unit.disable()
        self.status = StrategyStatus.STOPPED

    def on_tick(self, tick: dict, unit: AbstractUnit):
        pass

    def on_order(self, order: dict, unit: AbstractUnit):
        pass

    def on_trade(self, trade: dict, unit: AbstractUnit):
        pass

    def on_position(self, position_event: dict, unit: AbstractUnit):
        pass

    def on_account(self, account: dict):
        pass

    # ── 内部 ──

    def _route_tick(self, event):
        tick = event.data
        unit = self.get_unit(tick.get("instrument_id", ""))
        if unit is None:
            return
        if not unit.enabled:
            return
        if tick.get("last_price") is not None:
            unit.position.last_price = tick["last_price"]
        unit.on_tick(tick)
        self.on_tick(tick, unit)

    def _route_position(self, event):
        data = event.data
        inst_id = data.get("instrument_id", "")
        unit = self.get_unit(inst_id)
        if unit is None:
            return
        unit.position.update_from_ctp(
            posi_direction=data.get("posi_direction", ""),
            yd=data.get("yd_position", 0),
            today=data.get("today_position", 0),
            frozen=data.get("frozen", 0),
        )
        self.on_position(data, unit)

    def _route_account(self, event):
        self._last_account = dict(event.data)
        self.on_account(event.data)