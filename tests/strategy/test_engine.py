"""Step 5: StrategyEngine 测试"""
import pytest
from unittest.mock import MagicMock, call

from trader.event import EventType
from strategy.engine import StrategyEngine
from strategy.base import BaseStrategy, StrategyStatus
from strategy.unit import RealUnit


class FakeContract:
    def __init__(self, symbol, ctp_id):
        self.symbol = symbol
        self.ctp_id = ctp_id
        self.product_id = symbol[:2]


def make_real_unit(inst_id):
    c = FakeContract(symbol=inst_id, ctp_id=inst_id.lower())
    return RealUnit(inst_id, c, {})


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


@pytest.fixture
def engine():
    return StrategyEngine(
        event_engine=MagicMock(),
        td_gateway=MagicMock(),
        md_gateway=MagicMock(),
    )


class TestStrategyEngineRegister:
    def test_register_adds_strategy_to_dict(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        assert "test_strat" in engine.strategies
        assert engine.strategies["test_strat"] is s

    def test_register_sets_engine_reference(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        assert s.engine is engine

    def test_register_calls_on_init(self, engine):
        called = []

        class InitStrategy(BaseStrategy):
            def on_init(self):
                called.append(True)

        s = InitStrategy("test_strat")
        engine.register(s)
        assert len(called) == 1

    def test_unregister_removes_and_stops(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.unregister("test_strat")
        assert "test_strat" not in engine.strategies

    def test_unregister_does_nothing_for_missing(self, engine):
        engine.unregister("nonexistent")  # no error

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


class TestStrategyEngineStart:
    def test_start_registers_tick_handler(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        engine.event_engine.register.assert_any_call(
            EventType.TICK, s._route_tick
        )

    def test_start_registers_position_handler(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        engine.event_engine.register.assert_any_call(
            EventType.POSITION, s._route_position
        )

    def test_start_registers_account_handler(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.md_gateway.subscribe = MagicMock()
        engine.start("test_strat")
        engine.event_engine.register.assert_any_call(
            EventType.ACCOUNT, s._route_account
        )

    def test_start_subscribes_market_for_all_units(self, engine):
        s = DummyStrategy("test_strat")
        u1 = make_real_unit("rb2501")
        u2 = make_real_unit("rb2510")
        s.add_unit(u1)
        s.add_unit(u2)
        engine.register(s)
        engine.start("test_strat")
        assert engine.md_gateway.subscribe.call_count == 2
        engine.md_gateway.subscribe.assert_any_call("rb2501")
        engine.md_gateway.subscribe.assert_any_call("rb2510")

    def test_start_calls_strategy_on_start(self, engine):
        s = SpyStrategy("test_strat")
        engine.register(s)
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
        engine.event_engine.register.assert_not_called()

    def test_start_skips_if_not_registered(self, engine):
        engine.start("nonexistent")
        engine.event_engine.register.assert_not_called()


class TestStrategyEngineStop:
    def test_stop_calls_strategy_on_stop(self, engine):
        s = SpyStrategy("test_strat")
        engine.register(s)
        s.status = StrategyStatus.RUNNING
        engine.stop("test_strat")
        assert s.stop_called is True

    def test_stop_unregisters_tick_handler(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        s.status = StrategyStatus.RUNNING
        engine.stop("test_strat")
        engine.event_engine.unregister.assert_any_call(
            EventType.TICK, s._route_tick
        )

    def test_stop_unregisters_position_handler(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        s.status = StrategyStatus.RUNNING
        engine.stop("test_strat")
        engine.event_engine.unregister.assert_any_call(
            EventType.POSITION, s._route_position
        )

    def test_stop_unregisters_account_handler(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        s.status = StrategyStatus.RUNNING
        engine.stop("test_strat")
        engine.event_engine.unregister.assert_any_call(
            EventType.ACCOUNT, s._route_account
        )

    def test_stop_skips_if_not_running(self, engine):
        s = DummyStrategy("test_strat")
        engine.register(s)
        engine.stop("test_strat")  # status = STOPPED
        engine.event_engine.unregister.assert_not_called()


class TestStrategyEngineBulk:
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
        s1.status = StrategyStatus.RUNNING
        s2.status = StrategyStatus.RUNNING
        engine.stop_all()
        assert s1.status == StrategyStatus.STOPPED
        assert s2.status == StrategyStatus.STOPPED


class TestStrategyEngineEventRouting:
    def test_order_event_routes_to_correct_unit(self, engine):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501")
        s.add_unit(u)
        engine.register(s)
        engine.start("test_strat")

        # Get the registered ORDER handler
        order_calls = [
            c for c in engine.event_engine.register.call_args_list
            if c[0][0] == EventType.ORDER
        ]
        assert len(order_calls) == 1
        handler = order_calls[0][0][1]

        order_data = {"instrument_id": "rb2501", "order_ref": "123"}
        handler(MagicMock(data=order_data))

    def test_trade_event_routes_to_correct_unit(self, engine):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501")
        s.add_unit(u)
        engine.register(s)
        engine.start("test_strat")

        trade_calls = [
            c for c in engine.event_engine.register.call_args_list
            if c[0][0] == EventType.TRADE
        ]
        assert len(trade_calls) == 1
        handler = trade_calls[0][0][1]

        trade_data = {"instrument_id": "rb2501", "trade_id": "t001"}
        handler(MagicMock(data=trade_data))