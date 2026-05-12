from decimal import Decimal

import pytest

from src.common.commission import CommissionModel, CommissionRate, CommissionRule, CommissionType
from src.common.contract import Contract
from src.common.exchange import Exchange


def _rb2510() -> Contract:
    return Contract(
        instrument_id="rb2510",
        exchange=Exchange.SHFE,
        product_id="rb",
        year=25,
        month=10,
        multiplier=10,
        price_tick=Decimal("1"),
    )


class TestContract:
    def test_constructor(self):
        c = _rb2510()
        assert c.instrument_id == "rb2510"
        assert c.exchange == Exchange.SHFE
        assert c.product_id == "rb"
        assert c.year == 25
        assert c.month == 10
        assert c.multiplier == 10
        assert c.price_tick == Decimal("1")
        assert c.commission is None

    def test_repr(self):
        c = _rb2510()
        assert repr(c) == "Contract(instrument_id='rb2510', exchange=<Exchange.SHFE: 'SHFE'>, " \
                          "product_id='rb', year=25, month=10, multiplier=10, " \
                          "price_tick=Decimal('1'), commission=None)"

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
            product_id="m",
            year=26,
            month=9,
            multiplier=10,
            price_tick=Decimal("1"),
        )
        assert a != b

    def test_hashable(self):
        s = {_rb2510(), _rb2510()}
        assert len(s) == 1

    def test_with_commission(self):
        cm = CommissionModel(
            open_commission=CommissionRate(CommissionType.FIXED, Decimal("10")),
            close_commission=CommissionRate(CommissionType.FIXED, Decimal("10")),
            close_today_commission=CommissionRate(CommissionType.FIXED, Decimal("10")),
        )
        c = Contract(
            instrument_id="rb2510",
            exchange=Exchange.SHFE,
            product_id="rb",
            year=25,
            month=10,
            multiplier=10,
            price_tick=Decimal("1"),
            commission=cm,
        )
        assert c.commission is cm


class TestCommissionRate:
    def test_fixed_calculate(self):
        cr = CommissionRate(CommissionType.FIXED, Decimal("10"))
        assert cr.calculate(Decimal("3500"), 10, 5) == Decimal("50")

    def test_ratio_calculate(self):
        cr = CommissionRate(CommissionType.RATIO, Decimal("0.00005"))
        assert cr.calculate(Decimal("3500"), 10, 5) == Decimal("8.75")

    def test_fixed_repr(self):
        cr = CommissionRate(CommissionType.FIXED, Decimal("10"))
        assert repr(cr) == "10元/手"

    def test_ratio_repr(self):
        cr = CommissionRate(CommissionType.RATIO, Decimal("0.00005"))
        assert repr(cr) == "0.50万分之"


class TestCommissionModelCost:
    def test_open_fixed(self):
        cm = CommissionModel(
            open_commission=CommissionRate(CommissionType.FIXED, Decimal("10")),
            close_commission=CommissionRate(CommissionType.FIXED, Decimal("10")),
            close_today_commission=CommissionRate(CommissionType.FIXED, Decimal("5")),
        )
        assert cm.cost("open", Decimal("3500"), 10, 2) == Decimal("20")

    def test_close_uses_close_rate(self):
        cm = CommissionModel(
            open_commission=CommissionRate(CommissionType.FIXED, Decimal("10")),
            close_commission=CommissionRate(CommissionType.FIXED, Decimal("10")),
            close_today_commission=CommissionRate(CommissionType.FIXED, Decimal("5")),
        )
        assert cm.cost("close", Decimal("3500"), 10, 2) == Decimal("20")

    def test_close_today_uses_close_today_rate(self):
        cm = CommissionModel(
            open_commission=CommissionRate(CommissionType.FIXED, Decimal("10")),
            close_commission=CommissionRate(CommissionType.FIXED, Decimal("10")),
            close_today_commission=CommissionRate(CommissionType.FIXED, Decimal("5")),
        )
        assert cm.cost("close_today", Decimal("3500"), 10, 2) == Decimal("10")

    def test_open_ratio(self):
        cm = CommissionModel(
            open_commission=CommissionRate(CommissionType.RATIO, Decimal("0.00005")),
            close_commission=CommissionRate(CommissionType.RATIO, Decimal("0.00005")),
            close_today_commission=CommissionRate(CommissionType.RATIO, Decimal("0.00005")),
        )
        assert cm.cost("open", Decimal("3500"), 10, 2) == Decimal("3.5")