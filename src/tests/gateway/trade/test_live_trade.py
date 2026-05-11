"""Gateway integration tests shared by TTS and CTP backends.

Run connection/query tests:
    pytest -m "gateway and live" -v -s

Run order-placement tests:
    pytest -m "gateway and live_trade_window" -v -s
"""
import time

import pytest

from src.common.config import is_live_mode
from src.event_engine.event import EventType
from src.tests.gateway.trade._integration_support import EventCollector, GatewayIntegrationHarness


INSTRUMENT = "m2609"


@pytest.mark.live
@pytest.mark.gateway
class TestGatewayIntegration:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.harness = GatewayIntegrationHarness()
        yield
        self.harness.cleanup_positions()
        self.harness.close()

    def test_01_connect_and_login(self):
        td_login = self.harness.connect_td()
        md_login = self.harness.connect_md()

        assert self.harness.td_gw.status == "logined"
        assert self.harness.md_gw.status == "logined"

        backend_name = "CTP" if is_live_mode() else "TTS"
        print(f"\n[OK] backend={backend_name}")
        print(f"[OK] TD trading_day={td_login.get('trading_day', '')}")
        print(f"[OK] MD trading_day={md_login.get('trading_day', '')}")

    def test_02_query_account(self):
        self.harness.connect_td()

        account = EventCollector(self.harness.engine, EventType.ACCOUNT)
        self.harness.td_gw.query_account()
        event = account.wait(timeout=15)
        data = event.data

        print(
            f"\n[Account] id={data.get('account_id', '')} "
            f"balance={data.get('balance', 0):.2f} "
            f"available={data.get('available', 0):.2f}"
        )

    def test_03_query_positions(self):
        self.harness.connect_td()

        positions = EventCollector(self.harness.engine, EventType.POSITION)
        self.harness.td_gw.query_positions()
        time.sleep(2)
        self.harness.drain_events(iterations=30)

        print(f"\n[Positions] count={len(positions.events)}")
        for event in positions.events:
            data = event.data
            side = "long" if data["posi_direction"] == "2" else "short"
            print(
                f"  {data['instrument_id']} {side} "
                f"yd={data['yd_position']} td={data['today_position']}"
            )

    def test_04_subscribe_tick(self):
        self.harness.connect_md()
        tick = self.harness.wait_for_tick(INSTRUMENT)

        print(
            f"\n[Tick] {tick['instrument_id']} last={tick['last_price']} "
            f"bid1={tick['bid_price1']}/{tick['bid_volume1']} "
            f"ask1={tick['ask_price1']}/{tick['ask_volume1']}"
        )

    @pytest.mark.live_trade_window
    def test_05_open_long_and_close(self):
        self.harness.connect_td()
        self.harness.connect_md()

        tick = self.harness.wait_for_tick(INSTRUMENT)
        open_ref, open_trade = self.harness.place_and_collect_trade(
            INSTRUMENT, "buy", "open", tick["ask_price1"]
        )
        print(f"\n[Open] ref={open_ref}")
        assert open_trade.events, "expected trade event after opening position"

        close_tick_collector = EventCollector(self.harness.engine, EventType.TICK)
        self.harness.md_gw.subscribe(INSTRUMENT)
        close_tick = close_tick_collector.wait(timeout=15).data

        close_ref, close_trade = self.harness.place_and_collect_trade(
            INSTRUMENT, "sell", "close", close_tick["bid_price1"]
        )
        print(f"[Close] ref={close_ref}")
        assert len(close_trade.events) >= 1

    @pytest.mark.live_trade_window
    def test_06_settlement_confirm(self):
        self.harness.connect_td()

        settlement_info = EventCollector(self.harness.engine, EventType.SETTLEMENT_INFO)
        settlement_confirm = EventCollector(
            self.harness.engine, EventType.SETTLEMENT_INFO_CONFIRMED
        )

        self.harness.td_gw.qry_settlement_info()

        info_event = settlement_info.wait(timeout=15)
        confirm_event = settlement_confirm.wait(timeout=15)
        assert info_event.data["error_id"] == 0
        assert confirm_event.data["error_id"] == 0

    @pytest.mark.live_trade_window
    def test_07_cancel_order(self):
        self.harness.connect_td()
        self.harness.connect_md()

        tick = self.harness.wait_for_tick(INSTRUMENT)
        low_price = round(tick["bid_price1"] * 0.5, 0)
        orders = EventCollector(self.harness.engine, EventType.ORDER)

        order_ref = self.harness.td_gw.send_order(
            instrument_id=INSTRUMENT,
            direction="buy",
            offset_flag="open",
            price=low_price,
            volume=1,
        )
        time.sleep(1)
        self.harness.drain_events(iterations=30)

        self.harness.td_gw.cancel_order(
            instrument_id=INSTRUMENT,
            order_ref=order_ref,
            front_id=self.harness.td_gw.front_id,
            session_id=self.harness.td_gw.session_id,
        )
        time.sleep(3)
        self.harness.drain_events(iterations=30)

        matching_orders = [
            event.data for event in orders.events if event.data.get("order_ref") == order_ref
        ]
        assert matching_orders, "expected ORDER event for cancelled order"
        last_order = matching_orders[-1]
        assert (
            last_order.get("cancel_time")
            or "撤" in last_order.get("status_msg", "")
            or last_order.get("order_status") in ("5",)
        )
