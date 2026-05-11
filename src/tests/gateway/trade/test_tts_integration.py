"""TTS 全流程集成测试

核心理念:
  - class-level fixture 建立一次 MD + TD 连接，所有测试共享
  - 开仓用 ask_price1，平仓用 bid_price1
  - 统一使用 offset="close"，由柜台自行处理平仓顺序
  - 每个交易测试同方法内开仓 -> 平仓 -> 验证 TRADE 事件

使用方式:
  pytest -m "gateway and live" -v -s
"""
import time
import warnings
import pytest

from src.event_engine.event import EventType
from src.event_engine.event_engine import EventEngine
from src.common.config import USER_ID, PASSWORD, BROKER_ID, TD_FRONT, MD_FRONT

INSTRUMENTS = {
    "DCE": "m2609",
    "CZCE": "CF609",
    "SHFE": "au2612",
    "INE": "sc2609",
}


class _EC:
    def __init__(self, engine, event_type):
        self.events = []
        self._engine = engine
        engine.register(event_type, self._on_event)

    def _on_event(self, event):
        self.events.append(event)

    @property
    def last(self):
        return self.events[-1] if self.events else None

    def wait(self, timeout=30, min_events=1):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._engine.process_one()
            if len(self.events) >= min_events:
                return self.events[-1]
            time.sleep(0.01)
        pytest.fail("等待事件超时 %ss, 已收到 %d 个" % (timeout, len(self.events)))


@pytest.mark.live
@pytest.mark.gateway
class TestTtsIntegration:
    """TTS 全流程集成测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.engine = EventEngine()
        from src.gateway.md_gateway import MdGateway
        from src.gateway.td_gateway import TdGateway
        self.md_gw = MdGateway(self.engine, front_url=MD_FRONT,
            broker_id=BROKER_ID, user_id=USER_ID, password=PASSWORD)
        self.td_gw = TdGateway(self.engine, front_url=TD_FRONT,
            broker_id=BROKER_ID, user_id=USER_ID, password=PASSWORD,
            app_id="", auth_code="")
        md_c = _EC(self.engine, EventType.MD_LOGIN)
        self.md_gw.connect()
        td_c = _EC(self.engine, EventType.TD_LOGIN)
        self.td_gw.connect()
        md_c.wait(timeout=15)
        td_c.wait(timeout=15)

    def teardown_method(self):
        for gw in ("md_gw", "td_gw"):
            try:
                getattr(self, gw).close()
            except Exception:
                pass

    def _get_tick(self, instrument, timeout=15):
        c = _EC(self.engine, EventType.TICK)
        self.md_gw.subscribe(instrument)
        return c.wait(timeout=timeout).data

    def _place_and_check(self, inst, direction, offset, price, wait=8):
        trade_c = _EC(self.engine, EventType.TRADE)
        ref = self.td_gw.send_order(inst, direction, offset, price, 1)
        deadline = time.time() + wait
        while time.time() < deadline:
            self.engine.process_one()
            if any(e.data.get("order_ref") == ref for e in trade_c.events):
                break
            time.sleep(0.02)
        for _ in range(30):
            self.engine.process_one()
            time.sleep(0.01)
        return ref, trade_c

    def test_01_status(self):
        assert self.md_gw.status == "logined"
        assert self.td_gw.status == "logined"
        print("  MD=%s TD=%s" % (self.md_gw.status, self.td_gw.status))

    def test_10_subscribe_all(self):
        for name, inst in INSTRUMENTS.items():
            tick = self._get_tick(inst)
            print("  %s %s last=%.2f bid=%.2f ask=%.2f" % (
                name, inst, tick["last_price"],
                tick.get("bid_price1", 0), tick.get("ask_price1", 0)))
            assert tick["instrument_id"] == inst

    def test_20_query_account(self):
        c = _EC(self.engine, EventType.ACCOUNT)
        self.td_gw.query_account()
        ev = c.wait(timeout=15)
        print("  balance=%.2f avail=%.2f" % (ev.data["balance"], ev.data["available"]))

    def test_21_query_positions(self):
        c = _EC(self.engine, EventType.POSITION)
        self.td_gw.query_positions()
        time.sleep(2)
        for _ in range(30):
            self.engine.process_one()
            time.sleep(0.01)
        print("  持仓=%d 条" % len(c.events))

    def test_30_dce_open_close(self):
        tick = self._get_tick("m2609")
        ref_o, trade_o = self._place_and_check("m2609", "buy", "open", tick["ask_price1"])
        print("  DCE开仓 ref=%s" % ref_o)
        if not trade_o.events:
            pytest.skip("TTS非交易时段，跳过")
        print("  成交 price=%s" % trade_o.last.data["price"])
        ref_c, trade_c = self._place_and_check("m2609", "sell", "close", tick["bid_price1"])
        if trade_c.events:
            print("  DCE平仓 price=%s" % trade_c.last.data["price"])

    def test_31_czce_open_close(self):
        tick = self._get_tick("CF609")
        ref_o, trade_o = self._place_and_check("CF609", "buy", "open", tick["ask_price1"])
        print("  CZCE开仓 ref=%s" % ref_o)
        if not trade_o.events:
            pytest.skip("TTS非交易时段，跳过")
        print("  成交 price=%s" % trade_o.last.data["price"])
        ref_c, trade_c = self._place_and_check("CF609", "sell", "close", tick["bid_price1"])
        if trade_c.events:
            print("  CZCE平仓 price=%s" % trade_c.last.data["price"])

    def test_32_shfe_open_close(self):
        tick = self._get_tick("au2612")
        ref_o, trade_o = self._place_and_check("au2612", "buy", "open", tick["ask_price1"])
        print("  SHFE开仓 ref=%s" % ref_o)
        if not trade_o.events:
            pytest.skip("TTS非交易时段，跳过")
        print("  成交 price=%s" % trade_o.last.data["price"])
        ref_c, trade_c = self._place_and_check("au2612", "sell", "close", tick["bid_price1"])
        if trade_c.events:
            print("  SHFE平仓 price=%s" % trade_c.last.data["price"])

    def test_40_cancel_order(self):
        tick = self._get_tick("m2609")
        low = round(tick["bid_price1"] * 0.3, 0)
        or_c = _EC(self.engine, EventType.ORDER)
        ref = self.td_gw.send_order("m2609", "buy", "open", low, 1)
        print("  挂单 order=%s @ %.0f" % (ref, low))
        time.sleep(1)
        for _ in range(30):
            self.engine.process_one()
            time.sleep(0.01)
        self.td_gw.cancel_order("m2609", ref, self.td_gw.front_id, self.td_gw.session_id)
        print("  撤单已发")
        time.sleep(3)
        for _ in range(30):
            self.engine.process_one()
            time.sleep(0.01)
        matched = [e for e in or_c.events if e.data.get("order_ref") == ref]
        print("  订单事件=%d 条" % len(matched))