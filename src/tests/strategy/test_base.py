from decimal import Decimal

import pytest
from unittest.mock import MagicMock

from src.strategy.base import BaseStrategy, StrategyStatus
from src.common.position import Position
from src.common.exchange import Exchange
from src.common.contract import Contract


def make_contract(symbol, exchange=Exchange.SHFE):
    return Contract(
        instrument_id=symbol,
        exchange=exchange,
        product_id=symbol.rstrip("0123456789"),
        multiplier=10,
        price_tick=Decimal("1"),
    )


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

    def test_init_has_empty_contracts(self):
        s = DummyStrategy("test_strat")
        assert s.contracts == {}

    def test_tags_default_empty(self):
        s = DummyStrategy("test_strat")
        assert s.tags == set()

    def test_enabled_defaults_true(self):
        s = DummyStrategy("test_strat")
        assert s.enabled is True


class TestStrategyAddContract:
    def test_add_contract_stores_by_instrument_id(self):
        s = DummyStrategy("test_strat")
        c = make_contract("rb2501")
        s.add_contract(c)
        assert "rb2501" in s.contracts
        assert s.contracts["rb2501"] is c

    def test_add_contract_creates_position(self):
        s = DummyStrategy("test_strat")
        c = make_contract("rb2501")
        s.add_contract(c)
        assert "rb2501" in s.positions
        assert isinstance(s.positions["rb2501"], Position)
        assert s.positions["rb2501"].instrument_id == "rb2501"

    def test_add_contract_creates_tick_cache(self):
        s = DummyStrategy("test_strat")
        c = make_contract("rb2501")
        s.add_contract(c)
        assert "rb2501" in s.latest_ticks
        assert s.latest_ticks["rb2501"] == {}

    def test_subscribed_instrument_ids_reflects_contracts(self):
        s = DummyStrategy("test_strat")
        s.add_contract(make_contract("rb2501"))
        s.add_contract(make_contract("rb2510"))
        assert s.subscribed_instrument_ids() == {"rb2501", "rb2510"}


class TestStrategyHelpers:
    def test_price_returns_last_price(self):
        s = DummyStrategy("test_strat")
        s.latest_ticks["rb2501"] = {"last_price": 3500.0}
        assert s.price("rb2501") == 3500.0

    def test_price_returns_none_when_no_tick(self):
        s = DummyStrategy("test_strat")
        assert s.price("rb2501") is None

    def test_has_all_ticks_true_when_all_have_prices(self):
        s = DummyStrategy("test_strat")
        s.latest_ticks["rb2501"] = {"last_price": 3500.0}
        s.latest_ticks["rb2510"] = {"last_price": 3400.0}
        assert s.has_all_ticks("rb2501", "rb2510") is True

    def test_has_all_ticks_false_when_missing_price(self):
        s = DummyStrategy("test_strat")
        s.latest_ticks["rb2501"] = {"last_price": 3500.0}
        s.latest_ticks["rb2510"] = {}
        assert s.has_all_ticks("rb2501", "rb2510") is False


class TestStrategyLifecycle:
    def test_on_start_does_not_error(self):
        s = DummyStrategy("test_strat")
        s.on_start()

    def test_on_stop_sets_enabled_false_and_stopped(self):
        s = DummyStrategy("test_strat")
        s.on_stop()
        assert s.enabled is False
        assert s.status == StrategyStatus.STOPPED

    def test_enable_disable_toggle(self):
        s = DummyStrategy("test_strat")
        s.disable()
        assert s.enabled is False
        s.enable()
        assert s.enabled is True


class TestStrategyBuySell:
    def test_buy_delegates_to_runtime(self):
        s = DummyStrategy("test_strat")
        s.runtime = MagicMock()
        s.buy("rb2501", 3)
        s.runtime.send_order_for_strategy.assert_called_once_with(s, "rb2501", "buy", "open", 0, 3)

    def test_sell_delegates_to_runtime(self):
        s = DummyStrategy("test_strat")
        s.runtime = MagicMock()
        s.sell("rb2501", 2)
        s.runtime.send_order_for_strategy.assert_called_once_with(s, "rb2501", "sell", "open", 0, 2)

    def test_close_long_delegates_to_runtime(self):
        s = DummyStrategy("test_strat")
        s.runtime = MagicMock()
        s.close_long("rb2501", 1)
        s.runtime.send_order_for_strategy.assert_called_once_with(s, "rb2501", "sell", "close", 0, 1)

    def test_close_short_delegates_to_runtime(self):
        s = DummyStrategy("test_strat")
        s.runtime = MagicMock()
        s.close_short("rb2501", 1)
        s.runtime.send_order_for_strategy.assert_called_once_with(s, "rb2501", "buy", "close", 0, 1)

    def test_buy_with_price(self):
        s = DummyStrategy("test_strat")
        s.runtime = MagicMock()
        s.buy("rb2501", 3, 3510.0)
        s.runtime.send_order_for_strategy.assert_called_once_with(s, "rb2501", "buy", "open", 3510.0, 3)


class TestStrategyOnTick:
    def test_on_tick_is_callable(self):
        s = DummyStrategy("test_strat")
        tick = {"instrument_id": "rb2501", "last_price": 3500.0}
        s.on_tick(tick)

    def test_on_tick_skips_unknown_instrument(self):
        s = DummyStrategy("test_strat")
        tick = {"instrument_id": "unknown", "last_price": 100.0}
        s.on_tick(tick)


class TestStrategyOnOrder:
    def test_on_order_is_callable(self):
        s = DummyStrategy("test_strat")
        order = {"order_ref": "123", "instrument_id": "rb2501"}
        s.on_order(order)


class TestStrategyOnTrade:
    def test_on_trade_is_callable(self):
        s = DummyStrategy("test_strat")
        trade = {"trade_id": "t001", "instrument_id": "rb2501"}
        s.on_trade(trade)


class TestStrategyOnAccount:
    def test_on_account_receives_data(self):
        called = []

        class AccountStrategy(DummyStrategy):
            def on_account(self, account):
                called.append(account)

        s = AccountStrategy("test_strat")
        s.on_account({"balance": 100000.0})
        assert len(called) == 1
        assert called[0]["balance"] == 100000.0