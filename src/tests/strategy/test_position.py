"""Step 1: Position dataclass 测试"""
import pytest
from src.strategy.position import Position


class TestPositionDefaults:
    def test_default_position_is_all_zeros(self):
        p = Position(instrument_id="rb2501")
        assert p.instrument_id == "rb2501"
        assert p.long_yd == 0
        assert p.long_today == 0
        assert p.long_avg_price == 0.0
        assert p.long_frozen == 0
        assert p.short_yd == 0
        assert p.short_today == 0
        assert p.short_avg_price == 0.0
        assert p.short_frozen == 0
        assert p.last_price == 0.0
        assert p.unrealized_pnl == 0.0
        assert p.realized_pnl == 0.0

    def test_default_position_is_flat(self):
        p = Position(instrument_id="rb2501")
        assert p.is_flat is True
        assert p.is_long_only is False
        assert p.is_short_only is False
        assert p.long_volume == 0
        assert p.short_volume == 0
        assert p.net == 0


class TestPositionVolumes:
    def test_long_volume_sums_yd_and_today(self):
        p = Position(instrument_id="rb2501", long_yd=3, long_today=2)
        assert p.long_volume == 5

    def test_short_volume_sums_yd_and_today(self):
        p = Position(instrument_id="rb2501", short_yd=4, short_today=1)
        assert p.short_volume == 5

    def test_net_is_long_minus_short(self):
        p = Position(instrument_id="rb2501", long_yd=5, short_yd=3)
        assert p.net == 2

    def test_net_negative_when_short_greater(self):
        p = Position(instrument_id="rb2501", long_yd=2, short_yd=5)
        assert p.net == -3

    def test_net_zero_when_equal(self):
        p = Position(instrument_id="rb2501", long_yd=3, long_today=2, short_yd=5)
        assert p.net == 0

    def test_frozen_not_included_in_volume(self):
        p = Position(instrument_id="rb2501", long_today=5, long_frozen=2)
        assert p.long_volume == 5


class TestPositionDirectionFlags:
    def test_is_long_only_true_when_long_only(self):
        p = Position(instrument_id="rb2501", long_yd=3)
        assert p.is_long_only is True
        assert p.is_short_only is False

    def test_is_short_only_true_when_short_only(self):
        p = Position(instrument_id="rb2501", short_yd=3)
        assert p.is_short_only is True
        assert p.is_long_only is False

    def test_is_long_only_false_when_both_sides(self):
        p = Position(instrument_id="rb2501", long_yd=3, short_yd=1)
        assert p.is_long_only is False

    def test_is_short_only_false_when_both_sides(self):
        p = Position(instrument_id="rb2501", long_yd=3, short_yd=1)
        assert p.is_short_only is False

    def test_is_flat_false_when_has_long(self):
        p = Position(instrument_id="rb2501", long_yd=1)
        assert p.is_flat is False

    def test_is_flat_false_when_has_short(self):
        p = Position(instrument_id="rb2501", short_yd=1)
        assert p.is_flat is False

    def test_is_flat_false_when_has_both(self):
        p = Position(instrument_id="rb2501", long_yd=1, short_yd=1)
        assert p.is_flat is False

    def test_is_flat_true_when_both_zero_but_has_frozen(self):
        p = Position(instrument_id="rb2501", long_frozen=5)
        assert p.is_flat is True

    def test_is_flat_true_when_yd_zero_today_nonzero(self):
        p = Position(instrument_id="rb2501", long_today=2)
        assert p.is_flat is False


class TestPositionDynamicFields:
    def test_dynamic_fields_default_to_zero(self):
        p = Position(instrument_id="rb2501")
        assert p.last_price == 0.0
        assert p.unrealized_pnl == 0.0
        assert p.realized_pnl == 0.0

    def test_dynamic_fields_can_be_set(self):
        p = Position(instrument_id="rb2501", last_price=3500.0, unrealized_pnl=500.0, realized_pnl=200.0)
        assert p.last_price == 3500.0
        assert p.unrealized_pnl == 500.0
        assert p.realized_pnl == 200.0


class TestPositionDataclassBehavior:
    def test_equality_same_data(self):
        a = Position(instrument_id="rb2501", long_yd=5, short_yd=3)
        b = Position(instrument_id="rb2501", long_yd=5, short_yd=3)
        assert a == b

    def test_inequality_different_data(self):
        a = Position(instrument_id="rb2501", long_yd=5)
        b = Position(instrument_id="rb2501", long_yd=3)
        assert a != b

    def test_inequality_different_instrument(self):
        a = Position(instrument_id="rb2501", long_yd=5)
        b = Position(instrument_id="rb2510", long_yd=5)
        assert a != b

    def test_can_modify_after_creation(self):
        p = Position(instrument_id="rb2501")
        p.long_yd = 5
        p.short_yd = 3
        p.last_price = 3500.0
        assert p.long_yd == 5
        assert p.short_yd == 3
        assert p.long_volume == 5
        assert p.net == 2


class TestPositionUpdateFromCtp:
    def test_update_long_position_from_ctp(self):
        p = Position(instrument_id="rb2501")
        p.update_from_ctp(posi_direction="2", yd=5, today=3, frozen=1, avg_price=3500.0)
        assert p.long_yd == 5
        assert p.long_today == 3
        assert p.long_frozen == 1
        assert p.long_avg_price == 3500.0
        assert p.short_yd == 0
        assert p.short_today == 0

    def test_update_short_position_from_ctp(self):
        p = Position(instrument_id="m2609")
        p.update_from_ctp(posi_direction="3", yd=2, today=4, frozen=0, avg_price=2800.0)
        assert p.short_yd == 2
        assert p.short_today == 4
        assert p.short_frozen == 0
        assert p.short_avg_price == 2800.0
        assert p.long_yd == 0
        assert p.long_today == 0

    def test_update_overwrites_previous_values(self):
        p = Position(instrument_id="rb2501", long_yd=10, long_today=5, long_avg_price=3500.0)
        p.update_from_ctp(posi_direction="2", yd=3, today=1, frozen=0, avg_price=3550.0)
        assert p.long_yd == 3
        assert p.long_today == 1
        assert p.long_avg_price == 3550.0

    def test_update_does_not_affect_opposite_side(self):
        p = Position(instrument_id="rb2501", short_yd=5, short_today=3)
        p.update_from_ctp(posi_direction="2", yd=2, today=1, frozen=0, avg_price=3500.0)
        assert p.long_yd == 2
        assert p.short_yd == 5
        assert p.short_today == 3