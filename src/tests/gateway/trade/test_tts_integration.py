"""TTS-focused integration coverage built on the shared gateway harness."""
import pytest

from src.common.config import is_test_mode
from src.tests.gateway.trade._integration_support import GatewayIntegrationHarness


pytestmark = [pytest.mark.gateway, pytest.mark.live]

INSTRUMENTS = {
    "DCE": "m2609",
    "CZCE": "CF609",
    "SHFE": "au2612",
    "INE": "sc2609",
}


@pytest.mark.skipif(not is_test_mode(), reason="TTS-specific checks require TRADE_MODE=test")
class TestTtsIntegration:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.harness = GatewayIntegrationHarness()
        yield
        self.harness.cleanup_positions()
        self.harness.close()

    def test_subscribe_multiple_exchanges(self):
        self.harness.connect_md()

        for exchange_name, instrument_id in INSTRUMENTS.items():
            tick = self.harness.wait_for_tick(instrument_id)
            assert tick["instrument_id"] == instrument_id
            print(
                f"  {exchange_name} {instrument_id} "
                f"last={tick['last_price']:.2f} "
                f"bid={tick.get('bid_price1', 0):.2f} "
                f"ask={tick.get('ask_price1', 0):.2f}"
            )

    @pytest.mark.live_trade_window
    @pytest.mark.parametrize(
        ("instrument_id", "open_direction", "close_direction"),
        [
            ("m2609", "buy", "sell"),
            ("CF609", "buy", "sell"),
            ("au2612", "buy", "sell"),
        ],
    )
    def test_open_and_close_round_trip(self, instrument_id, open_direction, close_direction):
        self.harness.connect_td()
        self.harness.connect_md()

        tick = self.harness.wait_for_tick(instrument_id)
        open_ref, open_trades = self.harness.place_and_collect_trade(
            instrument_id, open_direction, "open", tick["ask_price1"]
        )
        print(f"  open {instrument_id} ref={open_ref}")
        assert open_trades.events, f"expected open trade event for {instrument_id}"

        refreshed_tick = self.harness.wait_for_tick(instrument_id)
        close_ref, close_trades = self.harness.place_and_collect_trade(
            instrument_id, close_direction, "close", refreshed_tick["bid_price1"]
        )
        print(f"  close {instrument_id} ref={close_ref}")
        assert close_trades.events, f"expected close trade event for {instrument_id}"
