"""Step 3: SyntheticUnit tests."""
from unittest.mock import MagicMock

from decimal import Decimal

from src.common.contract import Contract, parse_year_month
from src.common.exchange import Exchange
from src.common.position import Position
from src.strategy.unit import SyntheticUnit


def make_contract(symbol, exchange=Exchange.SHFE):
    year, month, product_id = parse_year_month(symbol)
    return Contract(
        instrument_id=symbol,
        exchange=exchange,
        product_id=product_id,
        year=year,
        month=month,
        multiplier=10,
        price_tick=Decimal("1"),
    )


class TestSyntheticUnitInit:
    def test_init_stores_components_and_weights(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        weights = [1.0, -1.0]
        unit = SyntheticUnit("spread_rb", comps, weights, {"threshold": 10})
        assert unit.components is comps
        assert unit.weights is weights
        assert unit.params == {"threshold": 10}

    def test_init_generates_formula_string(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        unit = SyntheticUnit("spread_rb", comps, [1.0, -1.0], {})
        assert "rb2501*1.0" in unit.formula
        assert "rb2510*-1.0" in unit.formula

    def test_init_formula_with_three_components(self):
        comps = [
            make_contract("rb2501"),
            make_contract("m2609", Exchange.DCE),
            make_contract("ta605", Exchange.CZCE),
        ]
        unit = SyntheticUnit("basket", comps, [0.5, 0.3, 0.2], {})
        assert unit.formula == "rb2501*0.5 + m2609*0.3 + ta605*0.2"

    def test_init_has_empty_price_cache(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        unit = SyntheticUnit("spread_rb", comps, [1.0, -1.0], {})
        assert unit._price_cache == {}

    def test_init_is_synthetic_true(self):
        unit = SyntheticUnit("test", [make_contract("rb2501")], [1.0], {})
        assert isinstance(unit, SyntheticUnit)

    def test_init_creates_position(self):
        unit = SyntheticUnit("test", [make_contract("rb2501")], [1.0], {})
        assert isinstance(unit.position, Position)
        assert unit.position.instrument_id == "test"

    def test_init_is_disabled_by_default(self):
        unit = SyntheticUnit("test", [make_contract("rb2501")], [1.0], {})
        assert unit.enabled is False


class TestSyntheticUnitSubscribeMarket:
    def test_subscribes_all_component_contracts(self):
        comps = [make_contract("rb2501"), make_contract("rb2510"), make_contract("rb2511")]
        unit = SyntheticUnit("spread_rb", comps, [1.0, -1.0, 0.5], {})
        md = MagicMock()
        unit.subscribe_market(md)
        assert md.subscribe.call_count == 3
        md.subscribe.assert_any_call("rb2501")
        md.subscribe.assert_any_call("rb2510")
        md.subscribe.assert_any_call("rb2511")


class TestSyntheticUnitOnTick:
    def _make_spread(self):
        comps = [make_contract("rb2501"), make_contract("rb2510")]
        unit = SyntheticUnit("spread_rb", comps, [1.0, -1.0], {})
        unit.enable()
        processed = []
        unit._process_tick = lambda tick: processed.append(tick)
        return unit, processed

    def test_does_not_process_when_disabled(self):
        unit = SyntheticUnit("spread_rb", [make_contract("rb2501"), make_contract("rb2510")], [1.0, -1.0], {})
        processed = []
        unit._process_tick = lambda tick: processed.append(tick)
        unit.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert processed == []

    def test_caches_first_component_price(self):
        unit, _ = self._make_spread()
        unit.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert unit._price_cache == {"rb2501": 3500.0}

    def test_caches_second_component_price(self):
        unit, _ = self._make_spread()
        unit.on_tick({"instrument_id": "rb2510", "last_price": 3400.0})
        assert unit._price_cache == {"rb2510": 3400.0}

    def test_processes_only_when_all_components_have_price(self):
        unit, processed = self._make_spread()
        unit.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert processed == []

        unit.on_tick({"instrument_id": "rb2510", "last_price": 3400.0})
        assert len(processed) == 1

    def test_computes_spread_price_correctly(self):
        unit, processed = self._make_spread()
        unit.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        unit.on_tick({"instrument_id": "rb2510", "last_price": 3400.0})

        tick = processed[0]
        assert tick["instrument_id"] == "spread_rb"
        assert tick["synthetic_price"] == 100.0
        assert tick["last_price"] == 100.0
        assert tick["source_instrument_id"] == "rb2510"
        assert tick["source_last_price"] == 3400.0

    def test_updates_cache_on_subsequent_ticks(self):
        unit, processed = self._make_spread()
        unit.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        unit.on_tick({"instrument_id": "rb2510", "last_price": 3400.0})
        assert len(processed) == 1

        unit.on_tick({"instrument_id": "rb2501", "last_price": 3510.0})
        assert len(processed) == 2
        assert processed[1]["synthetic_price"] == 110.0
        assert processed[1]["source_instrument_id"] == "rb2501"
        assert processed[1]["source_last_price"] == 3510.0

        unit.on_tick({"instrument_id": "rb2510", "last_price": 3410.0})
        assert len(processed) == 3
        assert processed[2]["synthetic_price"] == 100.0
        assert processed[2]["last_price"] == 100.0
        assert processed[2]["source_instrument_id"] == "rb2510"
        assert processed[2]["source_last_price"] == 3410.0

    def test_three_component_basket(self):
        comps = [
            make_contract("rb2501"),
            make_contract("m2609", Exchange.DCE),
            make_contract("ta605", Exchange.CZCE),
        ]
        unit = SyntheticUnit("basket", comps, [0.5, 0.3, 0.2], {})
        unit.enable()
        processed = []
        unit._process_tick = lambda tick: processed.append(tick)

        unit.on_tick({"instrument_id": "rb2501", "last_price": 100.0})
        unit.on_tick({"instrument_id": "m2609", "last_price": 200.0})
        unit.on_tick({"instrument_id": "ta605", "last_price": 300.0})

        assert len(processed) == 1
        assert processed[0]["synthetic_price"] == 170.0

    def test_ignores_tick_from_unrelated_instrument(self):
        unit, processed = self._make_spread()
        unit.on_tick({"instrument_id": "rb2505", "last_price": 9999.0})
        assert unit._price_cache == {}
        assert processed == []


class TestSyntheticUnitResetState:
    def test_reset_clears_price_cache(self):
        unit = SyntheticUnit(
            "spread_rb",
            [make_contract("rb2501"), make_contract("rb2510")],
            [1.0, -1.0],
            {},
        )
        unit.enable()
        unit.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert len(unit._price_cache) == 1

        unit._reset_state()
        assert unit._price_cache == {}

    def test_restart_clears_cache_and_enables(self):
        unit = SyntheticUnit(
            "spread_rb",
            [make_contract("rb2501"), make_contract("rb2510")],
            [1.0, -1.0],
            {},
        )
        unit.enable()
        unit.on_tick({"instrument_id": "rb2501", "last_price": 3500.0})
        assert len(unit._price_cache) == 1

        unit.disable()
        unit.restart()
        assert unit._price_cache == {}
        assert unit.enabled is True
