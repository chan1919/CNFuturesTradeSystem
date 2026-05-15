import time

import pytest

from src.common.config import (
    APP_ID,
    AUTH_CODE,
    BROKER_ID,
    MD_FRONT,
    PASSWORD,
    TD_FRONT,
    USER_ID,
    is_live_mode,
)
from src.event_bus.event import EventType
from src.event_bus.event_bus import EventBus
from src.logger.handler import LogHandler
from src.gateway.md_gateway import MdGateway
from src.gateway.td_gateway import TdGateway


def get_gateway_config() -> dict[str, str]:
    return {
        "user_id": USER_ID,
        "password": PASSWORD,
        "broker_id": BROKER_ID,
        "td_front": TD_FRONT,
        "md_front": MD_FRONT,
        "app_id": APP_ID,
        "auth_code": AUTH_CODE,
    }


class EventCollector:
    def __init__(self, event_bus, event_type):
        self.events = []
        self._event_bus = event_bus
        self._event_type = event_type
        event_bus.register(event_type, self._on_event)

    def _on_event(self, event):
        self.events.append(event)

    @property
    def last(self):
        return self.events[-1] if self.events else None

    def wait(self, timeout=30, min_events=1):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._event_bus.process_one()
            if len(self.events) >= min_events:
                return self.events[-1]
            time.sleep(0.01)
        pytest.fail(
            f"waiting for {self._event_type} timed out after {timeout}s; "
            f"received {len(self.events)} event(s)"
        )


class GatewayIntegrationHarness:
    def __init__(self):
        cfg = get_gateway_config()
        self.event_bus = EventBus()
        self.logger = LogHandler(self.event_bus)
        self.md_gw = MdGateway(
            self.event_bus,
            front_url=cfg["md_front"],
            broker_id=cfg["broker_id"],
            user_id=cfg["user_id"],
            password=cfg["password"],
        )
        self.td_gw = TdGateway(
            self.event_bus,
            front_url=cfg["td_front"],
            broker_id=cfg["broker_id"],
            user_id=cfg["user_id"],
            password=cfg["password"],
            app_id=cfg["app_id"],
            auth_code=cfg["auth_code"],
        )

    def close(self):
        for closer in (self.md_gw.close, self.td_gw.close, self.logger.close):
            try:
                closer()
            except Exception:
                pass

    def drain_events(self, iterations=20):
        for _ in range(iterations):
            self.event_bus.process_one()

    def connect_td(self, timeout=30):
        td_login = EventCollector(self.event_bus, EventType.TD_LOGIN)
        td_auth = EventCollector(self.event_bus, EventType.TD_AUTHENTICATE)
        self.td_gw.connect()

        if is_live_mode():
            td_auth.wait(timeout=min(timeout, 15))
            assert td_auth.last.data["error_id"] == 0, (
                f"trade authenticate failed: {td_auth.last.data.get('error_msg', '')}"
            )

        td_login.wait(timeout=timeout)
        data = td_login.last.data
        if data["error_id"] != 0:
            pytest.fail(f"trade login failed: {data.get('error_msg', '')}")
        return data

    def connect_md(self, timeout=15):
        md_login = EventCollector(self.event_bus, EventType.MD_LOGIN)
        self.md_gw.connect()
        md_login.wait(timeout=timeout)
        data = md_login.last.data
        if data["error_id"] != 0:
            pytest.fail(f"market login failed: {data.get('error_msg', '')}")
        return data

    def wait_for_tick(self, instrument_id, timeout=15):
        collector = EventCollector(self.event_bus, EventType.TICK)
        self.md_gw.subscribe(instrument_id)
        return collector.wait(timeout=timeout).data

    def place_and_collect_trade(self, instrument_id, direction, offset_flag, price, volume=1, wait=30):
        trades = EventCollector(self.event_bus, EventType.TRADE)
        order_ref = self.td_gw.send_order(instrument_id, direction, offset_flag, price, volume)
        deadline = time.time() + wait
        while time.time() < deadline:
            self.event_bus.process_one()
            if any(event.data.get("order_ref") == order_ref for event in trades.events):
                break
            time.sleep(0.02)
        self.drain_events(iterations=30)
        return order_ref, trades

    def cleanup_positions(self):
        if self.td_gw.status != "logined":
            return

        positions = EventCollector(self.event_bus, EventType.POSITION)
        self.td_gw.query_positions()
        time.sleep(2)
        self.drain_events(iterations=200)

        for position in positions.events:
            data = position.data
            total = data["yd_position"] + data["today_position"]
            if total <= 0:
                continue

            instrument_id = data["instrument_id"]
            close_direction = "sell" if data["direction"] == "long" else "buy"

            if self.md_gw.status not in ("connected", "logined"):
                self.connect_md()

            tick_collector = EventCollector(self.event_bus, EventType.TICK)
            self.md_gw.subscribe(instrument_id)
            try:
                tick_collector.wait(timeout=10)
            except Exception:
                continue

            if not tick_collector.events:
                continue

            tick = tick_collector.last.data
            close_price = tick["bid_price1"] if close_direction == "sell" else tick["ask_price1"]
            trade_collector = EventCollector(self.event_bus, EventType.TRADE)

            try:
                self.td_gw.send_order(instrument_id, close_direction, "close", close_price, total)
            except RuntimeError:
                pass
            time.sleep(3)
            self.drain_events(iterations=200)

            if trade_collector.events:
                continue

            try:
                self.td_gw.send_order(instrument_id, close_direction, "close_today", close_price, total)
            except RuntimeError:
                pass
            time.sleep(3)
            self.drain_events(iterations=200)
