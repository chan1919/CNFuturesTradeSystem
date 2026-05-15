from src.common.account import Account
from src.common.contract import Contract
from src.common.exchange import Exchange


def make_contract(symbol, exchange=Exchange.SHFE, multiplier=10, tick_size=1.0):
    return Contract(
        instrument_id=symbol,
        exchange=exchange,
        multiplier=multiplier,
        tick_size=tick_size,
    )


class TestAccountFunds:
    def test_default_funds_are_zero(self):
        acc = Account()
        assert acc.balance == 0.0
        assert acc.available == 0.0
        assert acc.curr_margin == 0.0
        assert acc.frozen_margin == 0.0
        assert acc.frozen_cash == 0.0
        assert acc.position_profit == 0.0
        assert acc.commission == 0.0
        assert acc.pre_balance == 0.0

    def test_update_from_query_sets_all_fields(self):
        acc = Account()
        acc.update_from_query({
            "balance": 150000.0,
            "available": 80000.0,
            "curr_margin": 50000.0,
            "frozen_margin": 10000.0,
            "frozen_cash": 5000.0,
            "position_profit": 12000.0,
            "commission": 3000.0,
            "pre_balance": 140000.0,
        })
        assert acc.balance == 150000.0
        assert acc.available == 80000.0
        assert acc.curr_margin == 50000.0
        assert acc.frozen_margin == 10000.0
        assert acc.frozen_cash == 5000.0
        assert acc.position_profit == 12000.0
        assert acc.commission == 3000.0
        assert acc.pre_balance == 140000.0

    def test_update_from_query_partial(self):
        acc = Account()
        acc.update_from_query({"balance": 100000.0})
        acc.update_from_query({"available": 60000.0, "balance": 90000.0})
        assert acc.balance == 90000.0
        assert acc.available == 60000.0

    def test_update_from_query_preserves_unspecified(self):
        acc = Account()
        acc.update_from_query({"balance": 100000.0})
        acc.update_from_query({"available": 60000.0})
        assert acc.balance == 100000.0  # 未指定的字段保持不变
        assert acc.available == 60000.0


class TestAccountCreate:
    def test_empty_account(self):
        acc = Account()
        assert acc.positions == {}

    def test_get_or_create_creates_position(self):
        acc = Account()
        c = make_contract("rb2501")
        pos = acc.get_or_create(c)
        assert pos.contract is c
        assert pos.instrument_id == "rb2501"
        assert pos.is_flat

    def test_get_or_create_returns_same_position(self):
        acc = Account()
        c = make_contract("rb2501")
        pos1 = acc.get_or_create(c)
        pos2 = acc.get_or_create(c)
        assert pos1 is pos2

    def test_get_position_returns_none_for_unknown(self):
        acc = Account()
        assert acc.get_position("nonexistent") is None

    def test_positions_property(self):
        acc = Account()
        acc.get_or_create(make_contract("rb2501"))
        acc.get_or_create(make_contract("rb2510"))
        assert len(acc.positions) == 2


class TestAccountGetAllPositions:
    def test_empty_account_returns_empty(self):
        assert Account().get_all_positions() == {}

    def test_flat_only_returns_empty(self):
        acc = Account()
        acc.get_or_create(make_contract("rb2501"))
        assert acc.get_all_positions() == {}

    def test_non_flat_returns_position(self):
        acc = Account()
        c = make_contract("rb2501")
        acc.apply_trade(c, "buy", "open", 3, 3500.0)
        result = acc.get_all_positions()
        assert len(result) == 1
        assert result["rb2501"].long_today == 3

    def test_mixed_flat_and_non_flat(self):
        acc = Account()
        acc.apply_trade(make_contract("rb2501"), "buy", "open", 3, 3500.0)
        acc.get_or_create(make_contract("rb2510"))
        result = acc.get_all_positions()
        assert len(result) == 1
        assert "rb2501" in result
        assert "rb2510" not in result

    def test_becomes_flat_after_full_close(self):
        acc = Account()
        c = make_contract("rb2501")
        acc.apply_trade(c, "buy", "open", 3, 3500.0)
        acc.apply_trade(c, "sell", "close", 3, 3550.0)
        assert acc.get_all_positions() == {}


class TestAccountApplyTrade:
    def test_apply_trade_creates_and_updates_position(self):
        acc = Account()
        c = make_contract("rb2501")
        acc.apply_trade(c, "buy", "open", 3, 3500.0)
        pos = acc.get_position("rb2501")
        assert pos is not None
        assert pos.long_today == 3

    def test_apply_trade_updates_existing_position(self):
        acc = Account()
        c = make_contract("rb2501")
        acc.apply_trade(c, "buy", "open", 3, 3500.0)
        acc.apply_trade(c, "sell", "close", 2, 3550.0)
        pos = acc.get_position("rb2501")
        assert pos.long_volume == 1


class TestAccountUpdateFromCtp:
    def test_update_long_from_ctp(self):
        acc = Account()
        c = make_contract("rb2501")
        acc.update_from_ctp("rb2501", c, direction="long", yd=5, today=3, frozen=1, avg_price=3500.0)
        pos = acc.get_position("rb2501")
        assert pos.long_yd == 5
        assert pos.long_today == 3
        assert pos.long_frozen == 1
        assert pos.long_avg_price == 3500.0

    def test_update_short_from_ctp(self):
        acc = Account()
        c = make_contract("rb2501")
        acc.update_from_ctp("rb2501", c, direction="short", yd=2, today=4, frozen=0, avg_price=2800.0)
        pos = acc.get_position("rb2501")
        assert pos.short_yd == 2
        assert pos.short_today == 4
        assert pos.short_avg_price == 2800.0

    def test_ctp_full_covering_long_then_short(self):
        acc = Account()
        c = make_contract("rb2501")
        acc.update_from_ctp("rb2501", c, direction="long", yd=5, today=3, frozen=1, avg_price=3500.0)
        acc.update_from_ctp("rb2501", c, direction="short", yd=2, today=4, frozen=0, avg_price=2800.0)
        pos = acc.get_position("rb2501")
        assert pos.long_yd == 5
        assert pos.short_yd == 2
        assert pos.net == 2

    def test_update_without_contract_does_not_create(self):
        acc = Account()
        acc.update_from_ctp("rb2501", None, direction="long", yd=5, today=3, avg_price=3500.0)
        assert acc.get_position("rb2501") is None