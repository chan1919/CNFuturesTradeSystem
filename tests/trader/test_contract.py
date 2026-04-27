"""TDD: Contract 合约类型 测试"""
import pytest
from trader.common.contract import Exchange, Contract, ctp_to_standard, standard_to_ctp


class TestExchangeEnum:
    def test_exchange_values(self):
        assert Exchange.SHFE.value == "SHFE"
        assert Exchange.DCE.value == "DCE"
        assert Exchange.CZCE.value == "CZCE"
        assert Exchange.CFFEX.value == "CFFEX"
        assert Exchange.INE.value == "INE"
        assert Exchange.GFEX.value == "GFEX"

    def test_czce_in_czce_set(self):
        assert Exchange.CZCE in Contract.CZCE_EXCHANGES

    def test_shfe_not_in_czce(self):
        assert Exchange.SHFE not in Contract.CZCE_EXCHANGES


class TestCtpToStandard:
    """CTP 原始格式 → 标准格式 (大写+4位数字)"""

    def test_shfe_lowercase_to_uppercase(self):
        assert ctp_to_standard("rb2510", Exchange.SHFE) == "RB2510"

    def test_dce_lowercase_to_uppercase(self):
        assert ctp_to_standard("m2609", Exchange.DCE) == "M2609"

    def test_czce_3digit_to_4digit(self):
        assert ctp_to_standard("CF609", Exchange.CZCE) == "CF2609"

    def test_czce_3digit_to_4digit_january(self):
        assert ctp_to_standard("SR601", Exchange.CZCE) == "SR2601"

    def test_czce_3digit_to_4digit_october(self):
        assert ctp_to_standard("MA610", Exchange.CZCE) == "MA2610"

    def test_czce_already_4digit_passthrough(self):
        assert ctp_to_standard("CF2609", Exchange.CZCE) == "CF2609"

    def test_czce_short_code(self):
        assert ctp_to_standard("CF09", Exchange.CZCE) == "CF09"

    def test_cffex_uppercase_passthrough(self):
        assert ctp_to_standard("IF2601", Exchange.CFFEX) == "IF2601"

    def test_ine_lowercase_to_uppercase(self):
        assert ctp_to_standard("sc2609", Exchange.INE) == "SC2609"

    def test_gfex_lowercase_to_uppercase(self):
        assert ctp_to_standard("si2609", Exchange.GFEX) == "SI2609"


class TestStandardToCtp:
    """标准格式 → CTP 原始格式 (下单用)"""

    def test_shfe_uppercase_to_lowercase(self):
        assert standard_to_ctp("RB2510", Exchange.SHFE) == "rb2510"

    def test_dce_uppercase_to_lowercase(self):
        assert standard_to_ctp("M2609", Exchange.DCE) == "m2609"

    def test_czce_remove_year_prefix(self):
        assert standard_to_ctp("CF2609", Exchange.CZCE) == "CF609"

    def test_czce_remove_year_prefix_january(self):
        assert standard_to_ctp("SR2601", Exchange.CZCE) == "SR601"

    def test_czce_remove_year_prefix_october(self):
        assert standard_to_ctp("MA2610", Exchange.CZCE) == "MA610"

    def test_cffex_uppercase_passthrough(self):
        assert standard_to_ctp("IF2601", Exchange.CFFEX) == "IF2601"

    def test_ine_uppercase_to_lowercase(self):
        assert standard_to_ctp("SC2609", Exchange.INE) == "sc2609"

    def test_gfex_uppercase_to_lowercase(self):
        assert standard_to_ctp("SI2609", Exchange.GFEX) == "si2609"


class TestContractFromCtp:
    """Contract.from_ctp() 工厂方法"""

    def test_from_ctp_shfe(self):
        c = Contract.from_ctp("rb2510", Exchange.SHFE)
        assert c.symbol == "RB2510"
        assert c.ctp_id == "rb2510"
        assert c.exchange == Exchange.SHFE
        assert c.product_id == "RB"
        assert c.year_month == "2510"
        assert c.year == 25
        assert c.month == 10

    def test_from_ctp_czce(self):
        c = Contract.from_ctp("CF609", Exchange.CZCE)
        assert c.symbol == "CF2609"
        assert c.ctp_id == "CF609"
        assert c.product_id == "CF"
        assert c.year_month == "2609"
        assert c.year == 26
        assert c.month == 9

    def test_from_ctp_dce(self):
        c = Contract.from_ctp("m2605", Exchange.DCE)
        assert c.symbol == "M2605"
        assert c.ctp_id == "m2605"
        assert c.product_id == "M"
        assert c.year_month == "2605"
        assert c.year == 26
        assert c.month == 5

    def test_from_ctp_cffex(self):
        c = Contract.from_ctp("IF2601", Exchange.CFFEX)
        assert c.symbol == "IF2601"
        assert c.ctp_id == "IF2601"
        assert c.product_id == "IF"

    def test_from_ctp_invalid_exchange_raises(self):
        with pytest.raises(ValueError):
            Contract.from_ctp("UNKNOWN", None)

    def test_repr(self):
        c = Contract.from_ctp("rb2510", Exchange.SHFE)
        assert repr(c) == "<Contract RB2510 SHFE>"

    def test_str(self):
        c = Contract.from_ctp("m2609", Exchange.DCE)
        assert str(c) == "M2609"

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

    def test_from_ctp_czce_full_examples(self):
        """验证几个真实 CZCE 合约"""
        cases = [
            ("CF609", Exchange.CZCE, "CF2609", "CF", "2609"),
            ("SR601", Exchange.CZCE, "SR2601", "SR", "2601"),
            ("TA605", Exchange.CZCE, "TA2605", "TA", "2605"),
            ("MA610", Exchange.CZCE, "MA2610", "MA", "2610"),
            ("AP610", Exchange.CZCE, "AP2610", "AP", "2610"),
            ("CJ609", Exchange.CZCE, "CJ2609", "CJ", "2609"),
        ]
        for ctp_id, exch, expected_symbol, expected_product, expected_ym in cases:
            c = Contract.from_ctp(ctp_id, exch)
            assert c.symbol == expected_symbol, f"{ctp_id} -> {expected_symbol}"
            assert c.product_id == expected_product, f"{ctp_id} -> product {expected_product}"
            assert c.year_month == expected_ym, f"{ctp_id} -> year_month {expected_ym}"

    def test_to_ctp_method(self):
        """Contract.to_ctp() 应返回 CTP 原始格式"""
        c = Contract.from_ctp("rb2510", Exchange.SHFE)
        assert c.to_ctp() == "rb2510"

        c = Contract.from_ctp("CF609", Exchange.CZCE)
        assert c.to_ctp() == "CF609"

        c = Contract.from_ctp("IF2601", Exchange.CFFEX)
        assert c.to_ctp() == "IF2601"