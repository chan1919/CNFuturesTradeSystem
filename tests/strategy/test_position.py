import pytest

from src.common.position import Position
from src.common.contract import Contract
from src.common.exchange import Exchange


def make_rb2510() -> Contract:
    return Contract(
        instrument_id="rb2510",
        exchange=Exchange.SHFE,
        multiplier=10,
        tick_size=1.0,
    )


def make_m2609() -> Contract:
    return Contract(
        instrument_id="m2609",
        exchange=Exchange.DCE,
        multiplier=10,
        tick_size=1.0,
    )


def make_if2601() -> Contract:
    return Contract(
        instrument_id="IF2601",
        exchange=Exchange.CFFEX,
        multiplier=300,
        tick_size=0.2,
    )


class TestPositionDefaults:
    def test_default_position_is_all_zeros(self):
        p = Position(contract=make_rb2510())
        assert p.instrument_id == "rb2510"
        assert p.long_yd == 0
        assert p.long_today == 0
        assert p.long_avg_price == 0.0
        assert p.long_frozen == 0
        assert p.short_yd == 0
        assert p.short_today == 0
        assert p.short_avg_price == 0.0
        assert p.short_frozen == 0
        assert p.last_price == 0.0
        assert p.realized_pnl == 0.0

    def test_default_position_is_flat(self):
        p = Position(contract=make_rb2510())
        assert p.is_flat is True
        assert p.is_long_only is False
        assert p.is_short_only is False
        assert p.long_volume == 0
        assert p.short_volume == 0
        assert p.net == 0

    def test_instrument_id_from_contract(self):
        p = Position(contract=make_rb2510())
        assert p.instrument_id == "rb2510"


class TestPositionVolumes:
    def test_long_volume_sums_yd_and_today(self):
        p = Position(contract=make_rb2510(), long_yd=3, long_today=2)
        assert p.long_volume == 5

    def test_short_volume_sums_yd_and_today(self):
        p = Position(contract=make_rb2510(), short_yd=4, short_today=1)
        assert p.short_volume == 5

    def test_net_is_long_minus_short(self):
        p = Position(contract=make_rb2510(), long_yd=5, short_yd=3)
        assert p.net == 2

    def test_net_negative_when_short_greater(self):
        p = Position(contract=make_rb2510(), long_yd=2, short_yd=5)
        assert p.net == -3

    def test_net_zero_when_equal(self):
        p = Position(contract=make_rb2510(), long_yd=3, long_today=2, short_yd=5)
        assert p.net == 0

    def test_frozen_not_included_in_volume(self):
        p = Position(contract=make_rb2510(), long_today=5, long_frozen=2)
        assert p.long_volume == 5


class TestPositionDirectionFlags:
    def test_is_long_only_true_when_long_only(self):
        p = Position(contract=make_rb2510(), long_yd=3)
        assert p.is_long_only is True
        assert p.is_short_only is False

    def test_is_short_only_true_when_short_only(self):
        p = Position(contract=make_rb2510(), short_yd=3)
        assert p.is_short_only is True
        assert p.is_long_only is False

    def test_is_long_only_false_when_both_sides(self):
        p = Position(contract=make_rb2510(), long_yd=3, short_yd=1)
        assert p.is_long_only is False

    def test_is_short_only_false_when_both_sides(self):
        p = Position(contract=make_rb2510(), long_yd=3, short_yd=1)
        assert p.is_short_only is False

    def test_is_flat_false_when_has_long(self):
        p = Position(contract=make_rb2510(), long_yd=1)
        assert p.is_flat is False

    def test_is_flat_false_when_has_short(self):
        p = Position(contract=make_rb2510(), short_yd=1)
        assert p.is_flat is False

    def test_is_flat_false_when_has_both(self):
        p = Position(contract=make_rb2510(), long_yd=1, short_yd=1)
        assert p.is_flat is False


class TestPositionPnL:
    def test_unrealized_pnl_long_only(self):
        p = Position(contract=make_rb2510(), long_yd=2, long_avg_price=3500.0, last_price=3550.0)
        assert p.unrealized_pnl == (3550.0 - 3500.0) * 10 * 2

    def test_unrealized_pnl_short_only(self):
        p = Position(contract=make_rb2510(), short_yd=3, short_avg_price=3400.0, last_price=3350.0)
        assert p.unrealized_pnl == (3400.0 - 3350.0) * 10 * 3

    def test_unrealized_pnl_both_sides(self):
        p = Position(contract=make_rb2510(),
                     long_yd=2, long_avg_price=3500.0,
                     short_yd=3, short_avg_price=3400.0,
                     last_price=3450.0)
        long_pnl = (3450.0 - 3500.0) * 10 * 2
        short_pnl = (3400.0 - 3450.0) * 10 * 3
        assert p.unrealized_pnl == long_pnl + short_pnl

    def test_unrealized_pnl_zero_when_flat(self):
        p = Position(contract=make_rb2510(), last_price=3500.0)
        assert p.unrealized_pnl == 0.0

    def test_unrealized_pnl_updates_with_last_price(self):
        p = Position(contract=make_rb2510(), long_yd=2, long_avg_price=3500.0, last_price=3550.0)
        p.update_last_price(3600.0)
        assert p.unrealized_pnl == (3600.0 - 3500.0) * 10 * 2

    def test_unrealized_pnl_respects_multiplier(self):
        p = Position(contract=make_if2601(), long_yd=1, long_avg_price=4000.0, last_price=4010.0)
        assert p.unrealized_pnl == (4010.0 - 4000.0) * 300 * 1

    def test_realized_pnl_starts_zero(self):
        p = Position(contract=make_rb2510())
        assert p.realized_pnl == 0.0

    def test_realized_pnl_on_long_close(self):
        p = Position(contract=make_rb2510(), long_yd=2, long_avg_price=3500.0)
        p.apply_trade("sell", "close", 1, 3550.0)
        assert p.realized_pnl == (3550.0 - 3500.0) * 10 * 1

    def test_realized_pnl_on_short_close(self):
        p = Position(contract=make_rb2510(), short_yd=2, short_avg_price=3400.0)
        p.apply_trade("buy", "close", 1, 3350.0)
        assert p.realized_pnl == (3400.0 - 3350.0) * 10 * 1

    def test_realized_pnl_accumulates(self):
        p = Position(contract=make_rb2510(), long_yd=5, long_avg_price=3500.0)
        p.apply_trade("sell", "close", 2, 3550.0)
        p.apply_trade("sell", "close", 1, 3600.0)
        expected = (3550.0 - 3500.0) * 10 * 2 + (3600.0 - 3500.0) * 10 * 1
        assert p.realized_pnl == expected


class TestPositionApplyTrade:
    def test_buy_open_adds_long_today(self):
        p = Position(contract=make_rb2510())
        p.apply_trade(direction="buy", offset="open", volume=3, price=3500.0)
        assert p.long_today == 3
        assert p.long_volume == 3
        assert p.long_avg_price == 3500.0

    def test_buy_open_updates_avg_price(self):
        p = Position(contract=make_rb2510(), long_today=2, long_avg_price=3000.0)
        p.apply_trade(direction="buy", offset="open", volume=3, price=3500.0)
        assert p.long_today == 5
        assert p.long_avg_price == 3300.0

    def test_sell_open_adds_short_today(self):
        p = Position(contract=make_rb2510())
        p.apply_trade(direction="sell", offset="open", volume=2, price=3400.0)
        assert p.short_today == 2
        assert p.short_volume == 2
        assert p.short_avg_price == 3400.0

    def test_buy_close_reduces_short(self):
        p = Position(contract=make_rb2510(), short_yd=5)
        p.apply_trade(direction="buy", offset="close", volume=3, price=3500.0)
        assert p.short_yd == 2
        assert p.short_volume == 2

    def test_sell_close_reduces_long(self):
        p = Position(contract=make_rb2510(), long_yd=5)
        p.apply_trade(direction="sell", offset="close", volume=3, price=3500.0)
        assert p.long_yd == 2
        assert p.long_volume == 2

    def test_close_does_not_go_below_zero(self):
        p = Position(contract=make_rb2510(), long_yd=2)
        p.apply_trade(direction="sell", offset="close", volume=5, price=3500.0)
        assert p.long_yd == 0
        assert p.long_volume == 0

    def test_sell_close_reduces_only_requested_volume_from_mixed_long(self):
        p = Position(contract=make_rb2510(), long_yd=2, long_today=3)
        p.apply_trade(direction="sell", offset="close", volume=1, price=3500.0)
        assert p.long_yd == 1
        assert p.long_today == 3
        assert p.long_volume == 4

    def test_buy_close_reduces_only_requested_volume_from_mixed_short(self):
        p = Position(contract=make_rb2510(), short_yd=2, short_today=3)
        p.apply_trade(direction="buy", offset="close", volume=1, price=3500.0)
        assert p.short_yd == 1
        assert p.short_today == 3
        assert p.short_volume == 4

    def test_close_today_reduces_today_bucket(self):
        p = Position(contract=make_rb2510(), long_yd=2, long_today=3)
        p.apply_trade(direction="sell", offset="close_today", volume=2, price=3500.0)
        assert p.long_yd == 2
        assert p.long_today == 1

    def test_close_yesterday_reduces_yd_bucket(self):
        p = Position(contract=make_rb2510(), long_yd=2, long_today=3)
        p.apply_trade(direction="sell", offset="close_yesterday", volume=2, price=3500.0)
        assert p.long_yd == 0
        assert p.long_today == 3