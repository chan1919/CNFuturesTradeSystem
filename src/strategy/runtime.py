from src.event_bus.event import EventType
from src.strategy.base import BaseStrategy, StrategyStatus


class StrategyRuntime:
    """策略运行时 — 注册、生命周期、事件路由

    tick 按 instrument_id 路由到订阅的策略。
    order/trade 按 order_ref 路由（非 instrument_id，避免多策略同合约时归属错误）。
    仓位管理由 Gateway 的 Account 统一处理，Runtime 只负责路由。
    """

    def __init__(self, event_bus, gateway):
        self.event_bus = event_bus
        self.gateway = gateway
        self.strategies: dict[str, BaseStrategy] = {}
        self._order_ref_to_strategy: dict[str, str] = {}
        self._instrument_to_strategies: dict[str, list[BaseStrategy]] = {}
        self._tick_handler = None
        self._order_handler = None
        self._trade_handler = None
        self._account_handler = None

    # ── 策略管理 ──

    def register(self, strategy: BaseStrategy):
        strategy.runtime = self
        strategy.on_init()
        self.strategies[strategy.name] = strategy
        for c in strategy.contracts.values():
            self.gateway.add_contract(c)
        for iid in strategy.subscribed_instrument_ids():
            self._instrument_to_strategies.setdefault(iid, []).append(strategy)

    def unregister(self, name: str):
        s = self.strategies.pop(name, None)
        if s is None:
            return
        if s.status == StrategyStatus.RUNNING:
            self._stop(s)
        else:
            s.on_stop()
        for iid in s.subscribed_instrument_ids():
            listeners = self._instrument_to_strategies.get(iid, [])
            if s in listeners:
                listeners.remove(s)
            if not listeners:
                self._instrument_to_strategies.pop(iid, None)

    def get(self, name: str) -> BaseStrategy | None:
        return self.strategies.get(name)

    def list_names(self) -> list[str]:
        return list(self.strategies.keys())

    def list_by_tag(self, tag: str) -> list[BaseStrategy]:
        return [s for s in self.strategies.values() if tag in s.tags]

    # ── 生命周期 ──

    def start(self, name: str):
        s = self.get(name)
        if not s or s.status != StrategyStatus.STOPPED:
            return
        self._ensure_running()
        s.status = StrategyStatus.STARTING
        s.enable()
        for iid in s.subscribed_instrument_ids():
            self.gateway.subscribe(iid)
        s.on_start()
        s.status = StrategyStatus.RUNNING

    def stop(self, name: str):
        s = self.get(name)
        if not s or s.status != StrategyStatus.RUNNING:
            return
        self._stop(s)

    def start_by_tag(self, tag: str):
        for s in self.list_by_tag(tag):
            self.start(s.name)

    def stop_by_tag(self, tag: str):
        for s in self.list_by_tag(tag):
            self.stop(s.name)

    def start_all(self):
        for name in self.list_names():
            self.start(name)

    def stop_all(self):
        for name in self.list_names():
            self.stop(name)

    # ── 聚合查询 ──

    def positions_by_tag(self, tag: str) -> dict[str, list]:
        result = {}
        for s in self.list_by_tag(tag):
            for iid in s.contracts:
                pos = self.gateway.account.get_position(iid)
                if pos:
                    result.setdefault(iid, []).append(pos)
        return result

    def trades_by_tag(self, tag: str) -> list[dict]:
        result = []
        for s in self.list_by_tag(tag):
            result.extend(s.trades.values())
        return result

    # ── 下单 ──

    def send_order_for_strategy(self, strategy: BaseStrategy, instrument_id: str,
                                direction: str, offset: str, price: float, volume: int):
        order_ref = self.gateway.send_order(instrument_id, direction, offset, price, volume)
        self._order_ref_to_strategy[order_ref] = strategy.name
        return order_ref

    # ── 内部 ──

    def _ensure_running(self):
        if self._tick_handler is not None:
            return
        self._tick_handler = self._on_tick
        self._order_handler = self._on_order
        self._trade_handler = self._on_trade
        self._account_handler = self._on_account
        self.event_bus.register(EventType.TICK, self._tick_handler)
        self.event_bus.register(EventType.ORDER, self._order_handler)
        self.event_bus.register(EventType.TRADE, self._trade_handler)
        self.event_bus.register(EventType.ACCOUNT, self._account_handler)

    def _stop(self, strategy: BaseStrategy):
        strategy.status = StrategyStatus.STOPPING
        strategy.on_stop()
        strategy.status = StrategyStatus.STOPPED

    def _on_tick(self, event):
        tick = event.data
        iid = tick.get("instrument_id", "")
        for s in self._instrument_to_strategies.get(iid, []):
            if not s.enabled or s.status != StrategyStatus.RUNNING:
                continue
            s.latest_ticks[iid] = tick
            s.on_tick(tick)

    def _on_order(self, event):
        order = event.data
        order_ref = order.get("order_ref", "")
        strategy_name = self._order_ref_to_strategy.get(order_ref)
        if strategy_name is None:
            return
        s = self.strategies.get(strategy_name)
        if s is None:
            return
        s.orders[order_ref] = order
        s.on_order(order)

    def _on_trade(self, event):
        trade = event.data
        order_ref = trade.get("order_ref", "")
        strategy_name = self._order_ref_to_strategy.get(order_ref)
        if strategy_name is None:
            return
        s = self.strategies.get(strategy_name)
        if s is None:
            return
        iid = trade.get("instrument_id", "")
        trade_id = trade.get("trade_id", "")
        s.trades[trade_id or str(len(s.trades))] = trade
        s.on_trade(trade)

    def _on_account(self, event):
        for s in self.strategies.values():
            s.on_account(event.data)