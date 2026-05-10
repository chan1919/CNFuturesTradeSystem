"""Step 2: AbstractUnit + RealUnit 测试"""
import pytest
from unittest.mock import MagicMock

from src.strategy.unit import AbstractUnit, RealUnit
from src.strategy.position import Position


class FakeContract:
    def __init__(self, symbol, ctp_id):
        self.symbol = symbol
        self.ctp_id = ctp_id


# ── 用一个具体子类来测试 AbstractUnit 的公共方法 ──

class DummyUnit(AbstractUnit):
    def subscribe_market(self, md):
        pass

    def on_tick(self, tick):
        pass

    def _process_tick(self, tick):
        pass


def make_contract(symbol="rb2501"):
    return FakeContract(symbol=symbol, ctp_id=symbol.lower())


class TestAbstractUnitInit:
    def test_init_sets_instrument_id_and_contract_and_params(self):
        c = make_contract("rb2501")
        u = DummyUnit("rb2501", c, {"fast": 5, "slow": 20})
        assert u.instrument_id == "rb2501"
        assert u.contract is c
        assert u.params == {"fast": 5, "slow": 20}

    def test_init_is_disabled_by_default(self):
        u = DummyUnit("rb2501", make_contract(), {})
        assert u.enabled is False

    def test_init_creates_position(self):
        u = DummyUnit("rb2501", make_contract(), {})
        assert isinstance(u.position, Position)
        assert u.position.instrument_id == "rb2501"


class TestAbstractUnitEnableDisable:
    def test_enable_sets_enabled_true(self):
        u = DummyUnit("rb2501", make_contract(), {})
        u.enable()
        assert u.enabled is True

    def test_disable_sets_enabled_false(self):
        u = DummyUnit("rb2501", make_contract(), {})
        u.enable()
        u.disable()
        assert u.enabled is False


class TestAbstractUnitParams:
    def test_update_params_merges_into_existing(self):
        u = DummyUnit("rb2501", make_contract(), {"fast": 5})
        u.update_params({"fast": 10, "slow": 20})
        assert u.params == {"fast": 10, "slow": 20}

    def test_update_params_preserves_untouched_keys(self):
        u = DummyUnit("rb2501", make_contract(), {"fast": 5, "slow": 20})
        u.update_params({"fast": 10})
        assert u.params == {"fast": 10, "slow": 20}


class TestAbstractUnitRestart:
    def test_restart_enables_the_unit(self):
        u = DummyUnit("rb2501", make_contract(), {})
        u.enable()
        u.disable()
        u.restart()
        assert u.enabled is True

    def test_restart_calls_reset_state(self):
        class SpiedUnit(DummyUnit):
            reset_called = False

            def _reset_state(self):
                super()._reset_state()
                self.reset_called = True

        u = SpiedUnit("rb2501", make_contract(), {})
        u.restart()
        assert u.reset_called is True


class TestRealUnitSubscribeMarket:
    def test_subscribe_market_calls_md_gateway_subscribe_with_ctp_id(self):
        c = make_contract("rb2501")
        u = RealUnit("rb2501", c, {})
        md = MagicMock()
        u.subscribe_market(md)
        md.subscribe.assert_called_once_with("rb2501")


class TestRealUnitOnTick:
    def test_on_tick_processes_when_enabled_and_matching_instrument(self):
        c = make_contract("rb2501")
        u = RealUnit("rb2501", c, {})
        u.enable()

        processed = []
        u._process_tick = lambda t: processed.append(t)

        tick = {"instrument_id": "rb2501", "last_price": 3500.0}
        u.on_tick(tick)
        assert len(processed) == 1
        assert processed[0]["last_price"] == 3500.0

    def test_on_tick_skips_when_disabled(self):
        c = make_contract("rb2501")
        u = RealUnit("rb2501", c, {})

        processed = []
        u._process_tick = lambda t: processed.append(t)

        u.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert len(processed) == 0

    def test_on_tick_skips_when_instrument_id_mismatch(self):
        c = make_contract("rb2501")
        u = RealUnit("rb2501", c, {})
        u.enable()

        processed = []
        u._process_tick = lambda t: processed.append(t)

        u.on_tick({"instrument_id": "rb2510", "last_price": 3600.0})
        assert len(processed) == 0

    def test_on_tick_uses_symbol_not_ctp_id_for_matching(self):
        c = make_contract("CF609")
        u = RealUnit("CF609", c, {})
        u.enable()

        processed = []
        u._process_tick = lambda t: processed.append(t)

        u.on_tick({"instrument_id": "CF609", "last_price": 500.0})
        assert len(processed) == 1