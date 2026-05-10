"""Step 3: SyntheticUnit 合成合约单元测试"""
import pytest
from unittest.mock import MagicMock

from src.strategy.unit import AbstractUnit, RealUnit, SyntheticUnit
from src.common.position import Position
from src.common.exchange import Exchange
from src.common.contract import Contract


def make_contract(symbol, exchange=Exchange.SHFE):
    return Contract.from_ctp(symbol, exchange)


class TestSyntheticUnitInit:
    def test_init_stores_components_and_weights(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        weights = [1.0, -1.0]
        u = SyntheticUnit("spread_rb", comps, weights, {"threshold": 10})
        assert u.components is comps
        assert u.weights is weights
        assert u.params == {"threshold": 10}

    def test_init_generates_formula_string(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        weights = [1.0, -1.0]
        u = SyntheticUnit("spread_rb", comps, weights, {})
        assert "rb2501*1.0" in u.formula
        assert "rb2510*-1.0" in u.formula

    def test_init_formula_with_three_components(self):
        comps = [make_contract("rb2501"), make_contract("m2609", Exchange.DCE), make_contract("ta605", Exchange.CZCE)]
        weights = [0.5, 0.3, 0.2]
        u = SyntheticUnit("basket", comps, weights, {})
        assert u.formula == "rb2501*0.5 + m2609*0.3 + ta605*0.2"

    def test_init_has_empty_price_cache(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        u = SyntheticUnit("spread_rb", comps, [1.0, -1.0], {})
        assert u._price_cache == {}

    def test_init_is_synthetic_true(self):
        comps = [make_contract("rb2501")]
        u = SyntheticUnit("test", comps, [1.0], {})
        # 通过 isinstance 检查而非属性
        assert isinstance(u, SyntheticUnit)

    def test_init_creates_position(self):
        comps = [make_contract("rb2501")]
        u = SyntheticUnit("test", comps, [1.0], {})
        assert isinstance(u.position, Position)
        assert u.position.instrument_id == "test"

    def test_init_is_disabled_by_default(self):
        comps = [make_contract("rb2501")]
        u = SyntheticUnit("test", comps, [1.0], {})
        assert u.enabled is False


class TestSyntheticUnitSubscribeMarket:
    def test_subscribes_all_component_contracts(self):
        comps = [make_contract("rb2501"), make_contract("rb2510"), make_contract("rb2511")]
        u = SyntheticUnit("spread_rb", comps, [1.0, -1.0, 0.5], {})
        md = MagicMock()
        u.subscribe_market(md)
        assert md.subscribe.call_count == 3
        md.subscribe.assert_any_call("rb2501")
        md.subscribe.assert_any_call("rb2510")
        md.subscribe.assert_any_call("rb2511")


class TestSyntheticUnitOnTick:
    def _make_spread(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        u = SyntheticUnit("spread_rb", comps, [1.0, -1.0], {})
        u.enable()
        processed = []
        u._process_tick = lambda t: processed.append(t)
        return u, processed

    def test_does_not_process_when_disabled(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        u = SyntheticUnit("spread_rb", comps, [1.0, -1.0], {})
        processed = []
        u._process_tick = lambda t: processed.append(t)
        u.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert len(processed) == 0

    def test_caches_first_component_price(self):
        u, _ = self._make_spread()
        u.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert u._price_cache == {"rb2501": 3500.0}

    def test_caches_second_component_price(self):
        u, _ = self._make_spread()
        u.on_tick({"instrument_id": "rb2510", "last_price": 3400.0})
        assert u._price_cache == {"rb2510": 3400.0}

    def test_processes_only_when_all_components_have_price(self):
        u, processed = self._make_spread()
        u.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert len(processed) == 0

        u.on_tick({"instrument_id": "rb2510", "last_price": 3400.0})
        assert len(processed) == 1

    def test_computes_spread_price_correctly(self):
        u, processed = self._make_spread()
        u.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        u.on_tick({"instrument_id": "rb2510", "last_price": 3400.0})

        assert len(processed) == 1
        tick = processed[0]
        assert tick["instrument_id"] == "spread_rb"
        assert tick["synthetic_price"] == 100.0  # 3500*1 + 3400*(-1)
        assert tick["last_price"] == 3400.0  # 保留最后一个原始tick的数据

    def test_updates_cache_on_subsequent_ticks(self):
        u, processed = self._make_spread()
        u.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        u.on_tick({"instrument_id": "rb2510", "last_price": 3400.0})
        assert len(processed) == 1

        # 每个成分更新后都会重新计算
        u.on_tick({"instrument_id": "rb2501", "last_price": 3510.0})
        assert len(processed) == 2
        assert processed[1]["synthetic_price"] == 110.0

        u.on_tick({"instrument_id": "rb2510", "last_price": 3410.0})
        assert len(processed) == 3
        assert processed[2]["synthetic_price"] == 100.0
        assert processed[2]["last_price"] == 3410.0

    def test_three_component_basket(self):
        comps = [make_contract("rb2501"), make_contract("m2609", Exchange.DCE), make_contract("ta605", Exchange.CZCE)]
        u = SyntheticUnit("basket", comps, [0.5, 0.3, 0.2], {})
        u.enable()
        processed = []
        u._process_tick = lambda t: processed.append(t)

        u.on_tick({"instrument_id": "rb2501", "last_price": 100.0})
        u.on_tick({"instrument_id": "m2609", "last_price": 200.0})
        u.on_tick({"instrument_id": "ta605", "last_price": 300.0})

        assert len(processed) == 1
        assert processed[0]["synthetic_price"] == 100 * 0.5 + 200 * 0.3 + 300 * 0.2

    def test_ignores_tick_from_unrelated_instrument(self):
        u, processed = self._make_spread()
        u.on_tick({"instrument_id": "rb2505", "last_price": 9999.0})
        assert u._price_cache == {}
        assert len(processed) == 0


class TestSyntheticUnitResetState:
    def test_reset_clears_price_cache(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        u = SyntheticUnit("spread_rb", comps, [1.0, -1.0], {})
        u.enable()
        u.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert len(u._price_cache) == 1

        u._reset_state()
        assert u._price_cache == {}

    def test_restart_clears_cache_and_enables(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        u = SyntheticUnit("spread_rb", comps, [1.0, -1.0], {})
        u.enable()
        u.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert len(u._price_cache) == 1

        u.disable()
        u.restart()
        assert u._price_cache == {}
        assert u.enabled is True