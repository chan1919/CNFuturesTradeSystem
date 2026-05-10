"""Step 4: BaseStrategy 测试"""
import pytest
from unittest.mock import MagicMock

from src.strategy.base import BaseStrategy, StrategyStatus
from src.strategy.unit import AbstractUnit, RealUnit
from src.strategy.position import Position


class FakeContract:
    def __init__(self, symbol, ctp_id):
        self.symbol = symbol
        self.ctp_id = ctp_id
        self.product_id = symbol[:2]


def make_contract(symbol):
    return FakeContract(symbol=symbol, ctp_id=symbol.lower())


def make_real_unit(inst_id, contract=None, params=None):
    c = contract or make_contract(inst_id)
    p = params or {}
    return RealUnit(inst_id, c, p)


class DummyStrategy(BaseStrategy):
    def on_init(self):
        pass


class TestStrategyInit:
    def test_init_sets_name(self):
        s = DummyStrategy("test_strat")
        assert s.name == "test_strat"

    def test_init_stopped_by_default(self):
        s = DummyStrategy("test_strat")
        assert s.status == StrategyStatus.STOPPED

    def test_init_has_empty_units(self):
        s = DummyStrategy("test_strat")
        assert s.units == {}


class TestStrategyUnitManagement:
    def test_add_unit_stores_by_instrument_id(self):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501")
        s.add_unit(u)
        assert "rb2501" in s.units
        assert s.units["rb2501"] is u

    def test_add_multiple_units(self):
        s = DummyStrategy("test_strat")
        u1 = make_real_unit("rb2501")
        u2 = make_real_unit("rb2510")
        s.add_unit(u1)
        s.add_unit(u2)
        assert len(s.units) == 2

    def test_get_unit_returns_none_for_missing(self):
        s = DummyStrategy("test_strat")
        assert s.get_unit("nonexistent") is None

    def test_get_unit_returns_unit_when_present(self):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501")
        s.add_unit(u)
        assert s.get_unit("rb2501") is u

    def test_remove_unit_returns_and_disables(self):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501")
        u.enable()
        s.add_unit(u)

        removed = s.get_unit("rb2501")
        s.remove_unit("rb2501")
        assert s.get_unit("rb2501") is None
        assert removed.enabled is False
        # verify it was only disabled, not destroyed
        assert removed.instrument_id == "rb2501"

    def test_list_unit_ids(self):
        s = DummyStrategy("test_strat")
        s.add_unit(make_real_unit("rb2501"))
        s.add_unit(make_real_unit("rb2510"))
        assert set(s.list_unit_ids()) == {"rb2501", "rb2510"}


class TestStrategyDelegation:
    def test_enable_delegates_to_unit(self):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501")
        s.add_unit(u)
        s.enable("rb2501")
        assert u.enabled is True

    def test_disable_delegates_to_unit(self):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501")
        u.enable()
        s.add_unit(u)
        s.disable("rb2501")
        assert u.enabled is False

    def test_update_params_delegates_to_unit(self):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501", params={"fast": 5})
        s.add_unit(u)
        s.update_params("rb2501", {"fast": 10})
        assert u.params == {"fast": 10}

    def test_restart_delegates_to_unit(self):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501")
        s.add_unit(u)
        s.disable("rb2501")
        s.restart("rb2501")
        assert u.enabled is True


class TestStrategyPositionQuery:
    def test_get_all_positions(self):
        s = DummyStrategy("test_strat")
        s.add_unit(make_real_unit("rb2501"))
        s.add_unit(make_real_unit("rb2510"))
        positions = s.get_all_positions()
        assert len(positions) == 2
        assert all(isinstance(p, Position) for p in positions)

    def test_get_positions_for_product(self):
        s = DummyStrategy("test_strat")
        c1 = FakeContract("rb2501", "rb2501")
        c1.product_id = "rb"
        c2 = FakeContract("rb2510", "rb2510")
        c2.product_id = "rb"
        c3 = FakeContract("m2609", "m2609")
        c3.product_id = "m"
        s.add_unit(make_real_unit("rb2501", c1))
        s.add_unit(make_real_unit("rb2510", c2))
        s.add_unit(make_real_unit("m2609", c3))

        rb_positions = s.get_positions_for("rb")
        assert len(rb_positions) == 2

    def test_get_positions_for_returns_empty_for_no_match(self):
        s = DummyStrategy("test_strat")
        s.add_unit(make_real_unit("rb2501"))
        positions = s.get_positions_for("m")
        assert positions == []


class TestStrategyLifecycle:
    def test_on_start_enables_all_units(self):
        s = DummyStrategy("test_strat")
        s.add_unit(make_real_unit("rb2501"))
        s.add_unit(make_real_unit("rb2510"))
        s.on_start()
        for u in s.units.values():
            assert u.enabled is True

    def test_on_stop_disables_all_units_and_sets_stopped(self):
        s = DummyStrategy("test_strat")
        s.add_unit(make_real_unit("rb2501"))
        s.add_unit(make_real_unit("rb2510"))
        s.on_start()
        s.on_stop()
        for u in s.units.values():
            assert u.enabled is False
        assert s.status == StrategyStatus.STOPPED


class TestStrategyRouteTick:
    def test_route_tick_to_correct_unit(self):
        class CaptureStrategy(DummyStrategy):
            def __init__(self, name):
                super().__init__(name)
                self.captured_ticks = []

            def on_tick(self, tick, unit):
                self.captured_ticks.append((tick, unit.instrument_id))

        s = CaptureStrategy("test_strat")
        u1 = make_real_unit("rb2501")
        u2 = make_real_unit("rb2510")
        u1.enable()
        u2.enable()
        s.add_unit(u1)
        s.add_unit(u2)

        event = MagicMock()
        event.data = {"instrument_id": "rb2510", "last_price": 3400.0}
        s._route_tick(event)

        assert len(s.captured_ticks) == 1
        assert s.captured_ticks[0][0]["last_price"] == 3400.0
        assert s.captured_ticks[0][1] == "rb2510"

    def test_route_tick_skips_when_unit_not_found(self):
        class CaptureStrategy(DummyStrategy):
            def on_tick(self, tick, unit):
                self.captured_ticks.append(tick)

        s = CaptureStrategy("test_strat")
        s.captured_ticks = []
        s.add_unit(make_real_unit("rb2501"))

        event = MagicMock()
        event.data = {"instrument_id": "rb9999", "last_price": 9999.0}
        s._route_tick(event)
        assert len(s.captured_ticks) == 0

    def test_route_tick_skips_when_unit_disabled(self):
        class CaptureStrategy(DummyStrategy):
            def on_tick(self, tick, unit):
                self.captured_ticks.append(tick)

        s = CaptureStrategy("test_strat")
        s.captured_ticks = []
        u = make_real_unit("rb2501")
        s.add_unit(u)

        event = MagicMock()
        event.data = {"instrument_id": "rb2501", "last_price": 3500.0}
        s._route_tick(event)
        assert len(s.captured_ticks) == 0


class TestStrategySyntheticUnits:
    def test_list_synthetic_units_filters_real_units(self):
        from src.strategy.unit import SyntheticUnit
        s = DummyStrategy("test_strat")
        s.add_unit(make_real_unit("rb2501"))
        comps = [FakeContract("rb2501", "rb2501"), FakeContract("rb2510", "rb2510")]
        s.add_unit(SyntheticUnit("spread", comps, [1.0, -1.0], {}))
        synthetics = s.list_synthetic_units()
        assert len(synthetics) == 1
        assert isinstance(synthetics[0], SyntheticUnit)


class TestStrategyRoutePosition:
    def test_route_position_updates_long_position(self):
        s = DummyStrategy("test_strat")
        u = make_real_unit("rb2501")
        s.add_unit(u)

        event = MagicMock()
        event.data = {
            "instrument_id": "rb2501",
            "posi_direction": "2",
            "yd_position": 5,
            "today_position": 3,
        }
        s._route_position(event)
        assert u.position.long_yd == 5
        assert u.position.long_today == 3

    def test_route_position_updates_short_position(self):
        s = DummyStrategy("test_strat")
        u = make_real_unit("m2609")
        s.add_unit(u)

        event = MagicMock()
        event.data = {
            "instrument_id": "m2609",
            "posi_direction": "3",
            "yd_position": 2,
            "today_position": 4,
        }
        s._route_position(event)
        assert u.position.short_yd == 2
        assert u.position.short_today == 4

    def test_route_position_skips_when_unit_not_found(self):
        s = DummyStrategy("test_strat")
        event = MagicMock()
        event.data = {"instrument_id": "rb9999", "posi_direction": "2", "yd_position": 5}
        s._route_position(event)  # no error


class TestStrategyRouteAccount:
    def test_route_account_stores_data(self):
        s = DummyStrategy("test_strat")
        event = MagicMock()
        event.data = {"balance": 150000.0, "available": 80000.0}
        s._route_account(event)
        assert s._last_account == {"balance": 150000.0, "available": 80000.0}


class TestStrategyTickUpdatesPrice:
    def test_on_tick_updates_last_price(self):
        class TrackingStrategy(DummyStrategy):
            def on_tick(self, tick, unit):
                pass

        s = TrackingStrategy("test_strat")
        u = make_real_unit("rb2501")
        u.enable()
        s.add_unit(u)

        event = MagicMock()
        event.data = {"instrument_id": "rb2501", "last_price": 3555.0}
        s._route_tick(event)
        assert u.position.last_price == 3555.0


class TestStrategyOrderAndTradeCallbacks:
    def test_on_order_callback_called(self):
        called = []

        class OStrategy(DummyStrategy):
            def on_order(self, order, unit):
                called.append((order["order_ref"], unit.instrument_id))

        s = OStrategy("test_strat")
        u = make_real_unit("rb2501")
        u.enable()
        s.add_unit(u)

        event = MagicMock()
        event.data = {"instrument_id": "rb2501", "order_ref": "5"}
        u.on_order = lambda e: s.on_order(e.data, u)
        u.on_order(event)

        assert len(called) == 1
        assert called[0] == ("5", "rb2501")

    def test_on_trade_callback_called(self):
        called = []

        class TStrategy(DummyStrategy):
            def on_trade(self, trade, unit):
                called.append((trade["trade_id"], unit.instrument_id))

        s = TStrategy("test_strat")
        u = make_real_unit("rb2501")
        u.enable()
        s.add_unit(u)

        event = MagicMock()
        event.data = {"instrument_id": "rb2501", "trade_id": "t99"}
        u.on_trade = lambda e: s.on_trade(e.data, u)
        u.on_trade(event)

        assert len(called) == 1
        assert called[0] == ("t99", "rb2501")