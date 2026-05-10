"""Step 2: AbstractUnit + RealUnit 测试"""
import pytest
from unittest.mock import MagicMock

from src.strategy.unit import AbstractUnit, RealUnit
from src.common.position import Position
from src.common.exchange import Exchange
from src.common.contract import Contract


class DummyUnit(AbstractUnit):
    def subscribe_market(self, md):
        pass

    def on_tick(self, tick):
        pass

    def _process_tick(self, tick):
        pass


def make_contract(instrument_id="rb2510", exchange=Exchange.SHFE):
    return Contract.from_ctp(instrument_id, exchange)


class TestAbstractUnitInit:
    def test_init_sets_instrument_id_and_contract_and_params(self):
        c = make_contract("rb2510")
        u = DummyUnit(c.instrument_id, c, {"fast": 5, "slow": 20})
        assert u.instrument_id == "rb2510"
        assert u.contract is c
        assert u.params == {"fast": 5, "slow": 20}

    def test_init_is_disabled_by_default(self):
        u = DummyUnit("rb2510", make_contract(), {})
        assert u.enabled is False

    def test_init_creates_position(self):
        u = DummyUnit("rb2510", make_contract(), {})
        assert isinstance(u.position, Position)
        assert u.position.instrument_id == "rb2510"


class TestAbstractUnitEnableDisable:
    def test_enable_sets_enabled_true(self):
        u = DummyUnit("rb2510", make_contract(), {})
        u.enable()
        assert u.enabled is True

    def test_disable_sets_enabled_false(self):
        u = DummyUnit("rb2510", make_contract(), {})
        u.enable()
        u.disable()
        assert u.enabled is False


class TestAbstractUnitParams:
    def test_update_params_merges_into_existing(self):
        u = DummyUnit("rb2510", make_contract(), {"fast": 5})
        u.update_params({"fast": 10, "slow": 20})
        assert u.params == {"fast": 10, "slow": 20}

    def test_update_params_preserves_untouched_keys(self):
        u = DummyUnit("rb2510", make_contract(), {"fast": 5, "slow": 20})
        u.update_params({"fast": 10})
        assert u.params == {"fast": 10, "slow": 20}


class TestAbstractUnitRestart:
    def test_restart_enables_the_unit(self):
        u = DummyUnit("rb2510", make_contract(), {})
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

        u = SpiedUnit("rb2510", make_contract(), {})
        u.restart()
        assert u.reset_called is True


class TestRealUnitSubscribeMarket:
    def test_subscribe_market_calls_md_gateway_subscribe_with_ctp_id(self):
        c = make_contract("rb2510")
        u = RealUnit(c.instrument_id, c, {})
        md = MagicMock()
        u.subscribe_market(md)
        md.subscribe.assert_called_once_with("rb2510")


class TestRealUnitOnTick:
    def test_on_tick_processes_when_enabled_and_matching_instrument(self):
        c = make_contract("rb2510")
        u = RealUnit(c.instrument_id, c, {})
        u.enable()

        processed = []
        u._process_tick = lambda t: processed.append(t)

        tick = {"instrument_id": "rb2510", "last_price": 3500.0}
        u.on_tick(tick)
        assert len(processed) == 1
        assert processed[0]["last_price"] == 3500.0

    def test_on_tick_skips_when_disabled(self):
        c = make_contract("rb2510")
        u = RealUnit(c.instrument_id, c, {})

        processed = []
        u._process_tick = lambda t: processed.append(t)

        u.on_tick({"instrument_id": "rb2510", "last_price": 3500.0})
        assert len(processed) == 0

    def test_on_tick_skips_when_instrument_id_mismatch(self):
        c = make_contract("rb2510")
        u = RealUnit(c.instrument_id, c, {})
        u.enable()

        processed = []
        u._process_tick = lambda t: processed.append(t)

        u.on_tick({"instrument_id": "rb2511", "last_price": 3600.0})
        assert len(processed) == 0

    def test_on_tick_czce_3digit_ctp_matches_ctp_id(self):
        c = make_contract("CF609", Exchange.CZCE)
        u = RealUnit(c.instrument_id, c, {})
        u.enable()

        processed = []
        u._process_tick = lambda t: processed.append(t)

        u.on_tick({"instrument_id": "CF609", "last_price": 500.0})
        assert len(processed) == 1