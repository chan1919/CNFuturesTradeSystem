import pytest
from src.common.exchange import Exchange
from src.common.contract import Contract


class TestExchangeEnum:
    def test_exchange_values(self):
        assert Exchange.SHFE.value == "SHFE"
        assert Exchange.DCE.value == "DCE"
        assert Exchange.CZCE.value == "CZCE"
        assert Exchange.CFFEX.value == "CFFEX"
        assert Exchange.INE.value == "INE"
        assert Exchange.GFEX.value == "GFEX"


class TestContractFromCtp:
    def test_from_ctp_shfe(self):
        c = Contract.from_ctp("rb2510", Exchange.SHFE)
        assert c.instrument_id == "rb2510"
        assert c.exchange == Exchange.SHFE
        assert c.product_id == "rb"
        assert c.year_month == "2510"
        assert c.year == 25
        assert c.month == 10

    def test_from_ctp_czce(self):
        c = Contract.from_ctp("CF609", Exchange.CZCE)
        assert c.instrument_id == "CF609"
        assert c.product_id == "CF"
        assert c.year_month == "2609"
        assert c.year == 26
        assert c.month == 9

    def test_from_ctp_dce(self):
        c = Contract.from_ctp("m2605", Exchange.DCE)
        assert c.instrument_id == "m2605"
        assert c.product_id == "m"
        assert c.year_month == "2605"
        assert c.year == 26
        assert c.month == 5

    def test_from_ctp_cffex(self):
        c = Contract.from_ctp("IF2601", Exchange.CFFEX)
        assert c.instrument_id == "IF2601"
        assert c.product_id == "IF"

    def test_from_ctp_invalid_exchange_raises(self):
        with pytest.raises(ValueError):
            Contract.from_ctp("UNKNOWN", None)

    def test_czce_full_examples(self):
        cases = [
            ("CF609", Exchange.CZCE, "CF", "2609"),
            ("SR601", Exchange.CZCE, "SR", "2601"),
            ("TA605", Exchange.CZCE, "TA", "2605"),
            ("MA610", Exchange.CZCE, "MA", "2610"),
        ]
        for ctp_id, exch, expected_product, expected_ym in cases:
            c = Contract.from_ctp(ctp_id, exch)
            assert c.product_id == expected_product, f"{ctp_id} -> product {expected_product}"
            assert c.year_month == expected_ym, f"{ctp_id} -> year_month {expected_ym}"
    def test_repr(self):
        c = Contract.from_ctp("rb2510", Exchange.SHFE)
        assert repr(c) == "<Contract rb2510 SHFE>"

    def test_str(self):
        c = Contract.from_ctp("m2609", Exchange.DCE)
        assert str(c) == "m2609"

    def test_eq_same_contract(self):
        c1 = Contract.from_ctp("rb2510", Exchange.SHFE)
        c2 = Contract.from_ctp("rb2510", Exchange.SHFE)
        assert c1 == c2

    def test_eq_different_contract(self):
        c1 = Contract.from_ctp("rb2510", Exchange.SHFE)
        c2 = Contract.from_ctp("rb2601", Exchange.SHFE)
        assert c1 != c2

    def test_hashable(self):
        c1 = Contract.from_ctp("rb2510", Exchange.SHFE)
        c2 = Contract.from_ctp("rb2510", Exchange.SHFE)
        s = {c1, c2}
        assert len(s) == 1