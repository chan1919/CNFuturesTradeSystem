import pytest
from unittest.mock import MagicMock, call

from src.event_bus.event import EventType
from src.strategy.runtime import StrategyRuntime
from src.strategy.base import BaseStrategy, StrategyStatus
from src.common.exchange import Exchange
from src.common.contract import Contract


class DummyStrategy(BaseStrategy):
    def on_init(self):
        pass


class SpyStrategy(BaseStrategy):
    def __init__(self, name):
        super().__init__(name)
        self.start_called = False
        self.stop_called = False

    def on_init(self):
        pass

    def on_start(self):
        super().on_start()
        self.start_called = True

    def on_stop(self):
        super().on_stop()
        self.stop_called = True


def make_contract(symbol, exchange=Exchange.SHFE):
    return Contract(
        instrument_id=symbol,
        exchange=exchange,
        multiplier=10,
        tick_size=1.0,
    )


@pytest.fixture
def engine():
    return StrategyRuntime(
        event_bus=MagicMock(),
        td_gateway=MagicMock(),
        md_gateway=MagicMock(),
    )


class TestStrategyRuntimeRegister:
    def test_register_adds_strategy_to_dict(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        assert "test_strat" in engine.strategies
        assert engine.strategies["test_strat"] is s

    def test_register_sets_runtime_reference(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        assert s.runtime is engine

    def test_register_calls_on_init(self, engine):
        called = []

        class InitStrategy(BaseStrategy):
            def on_init(self):
                called.append(True)

        s = InitStrategy("test_strat")
        engine.register(s)
        assert len(called) == 1

    def test_unregister_removes_strategy(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.unregister("test_strat")
        assert "test_strat" not in engine.strategies

    def test_unregister_does_nothing_for_missing(self, engine):
        engine.unregister("nonexistent")

    def test_get_returns_strategy(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        assert engine.get("test_strat") is s

    def test_get_returns_none_for_missing(self, engine):
        assert engine.get("nonexistent") is None

    def test_list_names(self, engine):
        engine.register(DummyStrategy("a"))
        engine.register(DummyStrategy("b"))
        assert set(engine.list_names()) == {"a", "b"}


class TestStrategyRuntimeStart:
    def test_start_registers_tick_handler(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        engine.event_bus.register.assert_any_call(EventType.TICK, engine._tick_handler)

    def test_start_subscribes_market_for_contracts(self, engine):
        s = DummyStrategy("test_strat")
        c1 = make_contract("rb2501")
        c2 = make_contract("rb2510")
        s.add_contract(c1)
        s.add_contract(c2)
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        assert engine.md_gateway.subscribe.call_count == 2
        engine.md_gateway.subscribe.assert_any_call("rb2501")
        engine.md_gateway.subscribe.assert_any_call("rb2510")

    def test_start_calls_strategy_on_start(self, engine):
        s = SpyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        assert s.start_called is True

    def test_start_sets_status_running(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        assert s.status == StrategyStatus.RUNNING

    def test_start_skips_if_not_stopped(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        s.status = StrategyStatus.RUNNING
        engine.start("test_strat")
        engine.event_bus.register.assert_not_called()

    def test_start_skips_if_not_registered(self, engine):
        engine.start("nonexistent")
        engine.event_bus.register.assert_not_called()

    def test_start_ensures_global_handlers_once(self, engine):
        s1 = DummyStrategy("a")
        s2 = DummyStrategy("b")
        engine.register(s1)
        engine.register(s2)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("a")
        engine.start("b")
        tick_registrations = [
            c for c in engine.event_bus.register.call_args_list
            if c[0][0] == EventType.TICK
        ]
        assert len(tick_registrations) == 1


class TestStrategyRuntimeStop:
    def test_stop_calls_strategy_on_stop(self, engine):
        s = SpyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        engine.stop("test_strat")
        assert s.stop_called is True

    def test_stop_sets_status_stopped(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        engine.stop("test_strat")
        assert s.status == StrategyStatus.STOPPED

    def test_start_after_stop_reenables_tick_routing(self, engine):
        s = DummyStrategy("test_strat")
        s.add_contract(make_contract("rb2501"))
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        engine.stop("test_strat")
        engine.start("test_strat")

        engine._on_tick(MagicMock(data={"instrument_id": "rb2501", "last_price": 3500.0}))

        assert s.enabled is True
        assert s.latest_ticks["rb2501"]["last_price"] == 3500.0

    def test_stop_skips_if_not_running(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.stop("test_strat")
        engine.event_bus.unregister.assert_not_called()


class TestStrategyRuntimeBulk:
    def test_start_all_sets_all_running(self, engine):
        s1 = DummyStrategy("a")
        s2 = DummyStrategy("b")
        engine.register(s1)
        engine.register(s2)
        engine.md_gateway.subscribe = MagicMock()
        engine.start_all()
        assert s1.status == StrategyStatus.RUNNING
        assert s2.status == StrategyStatus.RUNNING

    def test_stop_all_stops_all(self, engine):
        s1 = DummyStrategy("a")
        s2 = DummyStrategy("b")
        engine.register(s1)
        engine.register(s2)
        engine.md_gateway.subscribe = MagicMock()
        engine.start_all()
        engine.stop_all()
        assert s1.status == StrategyStatus.STOPPED
        assert s2.status == StrategyStatus.STOPPED


class TestStrategyRuntimeTagControl:
    def test_list_by_tag(self, engine):
        s1 = DummyStrategy("a")
        s2 = DummyStrategy("b")
        s3 = DummyStrategy("c")
        s1.tags.add("macd")
        s2.tags.add("macd")
        s3.tags.add("arbitrage")
        engine.register(s1)
        engine.register(s2)
        engine.register(s3)
        macd_strats = engine.list_by_tag("macd")
        assert len(macd_strats) == 2
        assert s1 in macd_strats
        assert s2 in macd_strats

    def test_start_by_tag(self, engine):
        s1 = DummyStrategy("a")
        s2 = DummyStrategy("b")
        s1.tags.add("macd")
        s2.tags.add("other")
        engine.register(s1)
        engine.register(s2)
        engine.md_gateway.subscribe = MagicMock()
        engine.start_by_tag("macd")
        assert s1.status == StrategyStatus.RUNNING
        assert s2.status == StrategyStatus.STOPPED

    def test_stop_by_tag(self, engine):
        s1 = DummyStrategy("a")
        s2 = DummyStrategy("b")
        s1.tags.add("macd")
        s2.tags.add("macd")
        engine.register(s1)
        engine.register(s2)
        engine.md_gateway.subscribe = MagicMock()
        engine.start_all()
        engine.stop_by_tag("macd")
        assert s1.status == StrategyStatus.STOPPED
        assert s2.status == StrategyStatus.STOPPED

    def test_positions_by_tag(self, engine):
        s = DummyStrategy("test_strat")
        s.tags.add("macd")
        c = make_contract("rb2501")
        s.add_contract(c)
        engine.register(s)
        result = engine.positions_by_tag("macd")
        assert "rb2501" in result
        assert len(result["rb2501"]) == 1

    def test_positions_by_tag_returns_empty_for_no_match(self, engine):
        assert engine.positions_by_tag("nonexistent") == {}

    def test_trades_by_tag(self, engine):
        s = DummyStrategy("test_strat")
        s.tags.add("macd")
        s.trades["t001"] = {"trade_id": "t001"}
        engine.register(s)
        result = engine.trades_by_tag("macd")
        assert len(result) == 1
        assert result[0]["trade_id"] == "t001"

    def test_trades_by_tag_returns_empty_for_no_match(self, engine):
        assert engine.trades_by_tag("nonexistent") == []


class TestStrategyRuntimeTickRouting:
    def test_tick_routes_to_subscribed_strategies(self, engine):
        s = DummyStrategy("test_strat")
        c = make_contract("rb2501")
        s.add_contract(c)
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")

        tick_data = {"instrument_id": "rb2501", "last_price": 3500.0}
        engine._on_tick(MagicMock(data=tick_data))
        assert s.latest_ticks.get("rb2501", {}).get("last_price") == 3500.0
        assert s.positions["rb2501"].last_price == 3500.0

    def test_tick_does_not_route_to_unsubscribed(self, engine):
        s = DummyStrategy("test_strat")
        c = make_contract("rb2501")
        s.add_contract(c)
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")

        tick_data = {"instrument_id": "rb2510", "last_price": 3400.0}
        engine._on_tick(MagicMock(data=tick_data))
        assert s.latest_ticks.get("rb2501", {}).get("last_price") is None

    def test_tick_routes_to_multiple_strategies(self, engine):
        s1 = DummyStrategy("a")
        s2 = DummyStrategy("b")
        c = make_contract("rb2501")
        s1.add_contract(c)
        s2.add_contract(c)
        engine.register(s1)
        engine.register(s2)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("a")
        engine.start("b")

        tick_data = {"instrument_id": "rb2501", "last_price": 3500.0}
        engine._on_tick(MagicMock(data=tick_data))
        assert s1.latest_ticks["rb2501"]["last_price"] == 3500.0
        assert s2.latest_ticks["rb2501"]["last_price"] == 3500.0


class TestStrategyRuntimeOrderRouting:
    def test_order_routes_by_order_ref(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")

        engine._order_ref_to_strategy["123"] = "test_strat"
        order_data = {"order_ref": "123", "instrument_id": "rb2501", "order_status": "0"}
        engine._on_order(MagicMock(data=order_data))
        assert s.orders.get("123", {}).get("order_status") == "0"

    def test_order_skips_unknown_order_ref(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")

        order_data = {"order_ref": "999", "instrument_id": "rb2501"}
        engine._on_order(MagicMock(data=order_data))
        assert len(s.orders) == 0


class TestStrategyRuntimeTradeRouting:
    def test_trade_routes_by_order_ref(self, engine):
        s = DummyStrategy("test_strat")
        c = make_contract("rb2501")
        s.add_contract(c)
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")

        engine._order_ref_to_strategy["123"] = "test_strat"
        trade_data = {
            "trade_id": "t001",
            "order_ref": "123",
            "instrument_id": "rb2501",
            "direction": "buy",
            "offset_flag": "open",
            "volume": 3,
            "price": 3500.0,
        }
        engine._on_trade(MagicMock(data=trade_data))
        assert s.trades.get("t001", {}).get("trade_id") == "t001"
        assert s.positions["rb2501"].long_today == 3

    def test_trade_routes_ctp_enum_values_to_position(self, engine):
        s = DummyStrategy("test_strat")
        s.add_contract(make_contract("rb2501"))
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")

        engine._order_ref_to_strategy["123"] = "test_strat"
        trade_data = {
            "trade_id": "t001",
            "order_ref": "123",
            "instrument_id": "rb2501",
            "direction": "0",
            "offset_flag": "0",
            "volume": 3,
            "price": 3500.0,
        }
        engine._on_trade(MagicMock(data=trade_data))

        assert s.positions["rb2501"].long_today == 3

    def test_trade_skips_unknown_order_ref(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")

        trade_data = {"trade_id": "t001", "order_ref": "999"}
        engine._on_trade(MagicMock(data=trade_data))
        assert len(s.trades) == 0


class TestStrategyRuntimeSendOrder:
    def test_send_order_for_strategy(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")

        engine.td_gateway.send_order = MagicMock(return_value="456")
        ref = engine.send_order_for_strategy(s, "rb2501", "buy", "open", 3500.0, 2)
        assert ref == "456"
        assert engine._order_ref_to_strategy["456"] == "test_strat"
        engine.td_gateway.send_order.assert_called_once_with("rb2501", "buy", "open", 3500.0, 2)
