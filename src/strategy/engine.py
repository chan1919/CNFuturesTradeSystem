from src.trader.event import EventType
from src.strategy.base import BaseStrategy, StrategyStatus


class StrategyEngine:
    def __init__(self, event_engine, td_gateway, md_gateway):
        self.event_engine = event_engine
        self.td_gateway = td_gateway
        self.md_gateway = md_gateway
        self.strategies: dict[str, BaseStrategy] = {}
        self._order_handlers: dict[str, callable] = {}
        self._trade_handlers: dict[str, callable] = {}

    # ── 策略管理 ──

    def register(self, strategy: BaseStrategy):
        strategy.engine = self
        strategy.on_init()
        self.strategies[strategy.name] = strategy

    def unregister(self, name: str):
        s = self.strategies.pop(name, None)
        if s:
            s.on_stop()

    def get(self, name: str) -> BaseStrategy | None:
        return self.strategies.get(name)

    def list_names(self) -> list[str]:
        return list(self.strategies.keys())

    # ── 生命周期 ──

    def start(self, name: str):
        s = self.get(name)
        if not s or s.status != StrategyStatus.STOPPED:
            return
        s.status = StrategyStatus.STARTING
        self.event_engine.register(EventType.TICK, s._route_tick)
        self.event_engine.register(EventType.POSITION, s._route_position)
        self.event_engine.register(EventType.ACCOUNT, s._route_account)
        self._order_handlers[name] = self._make_on_order(s)
        self._trade_handlers[name] = self._make_on_trade(s)
        self.event_engine.register(EventType.ORDER, self._order_handlers[name])
        self.event_engine.register(EventType.TRADE, self._trade_handlers[name])
        for unit in s.units.values():
            unit.subscribe_market(self.md_gateway)
        s.on_start()
        s.status = StrategyStatus.RUNNING

    def stop(self, name: str):
        s = self.get(name)
        if not s or s.status != StrategyStatus.RUNNING:
            return
        s.status = StrategyStatus.STOPPING
        s.on_stop()
        self.event_engine.unregister(EventType.TICK, s._route_tick)
        self.event_engine.unregister(EventType.POSITION, s._route_position)
        self.event_engine.unregister(EventType.ACCOUNT, s._route_account)
        if name in self._order_handlers:
            self.event_engine.unregister(EventType.ORDER, self._order_handlers.pop(name))
        if name in self._trade_handlers:
            self.event_engine.unregister(EventType.TRADE, self._trade_handlers.pop(name))

    def start_all(self):
        for name in self.list_names():
            self.start(name)

    def stop_all(self):
        for name in self.list_names():
            self.stop(name)

    # ── 内部 ──

    def _make_on_order(self, strategy):
        def handler(event):
            order = event.data
            unit = strategy.get_unit(order.get("instrument_id", ""))
            if unit:
                unit.on_order(event)
        return handler

    def _make_on_trade(self, strategy):
        def handler(event):
            trade = event.data
            unit = strategy.get_unit(trade.get("instrument_id", ""))
            if unit:
                unit.on_trade(event)
        return handler