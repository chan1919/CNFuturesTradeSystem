import pytest

from src.common.contract import Contract
from src.common.exchange import Exchange


def _rb2510() -> Contract:
    return Contract(
        instrument_id="rb2510",
        exchange=Exchange.SHFE,
        multiplier=10,
        tick_size=1.0,
    )


class TestContract:
    def test_constructor(self):
        c = _rb2510()
        assert c.instrument_id == "rb2510"
        assert c.exchange == Exchange.SHFE
        assert c.multiplier == 10
        assert c.tick_size == 1.0

    def test_str(self):
        c = _rb2510()
        assert str(c) == "rb2510"

    def test_eq_same(self):
        assert _rb2510() == _rb2510()

    def test_eq_different(self):
        a = _rb2510()
        b = Contract(
            instrument_id="m2609",
            exchange=Exchange.DCE,
            multiplier=10,
            tick_size=1.0,
        )
        assert a != b

    def test_hashable(self):
        s = {_rb2510(), _rb2510()}
        assert len(s) == 1

    def test_czce_preserves_case(self):
        c = Contract(
            instrument_id="CF609",
            exchange=Exchange.CZCE,
            multiplier=5,
            tick_size=1.0,
        )
        assert c.instrument_id == "CF609"

    def test_cffex_preserves_case(self):
        c = Contract(
            instrument_id="IF2601",
            exchange=Exchange.CFFEX,
            multiplier=300,
            tick_size=0.2,
        )
        assert c.instrument_id == "IF2601"