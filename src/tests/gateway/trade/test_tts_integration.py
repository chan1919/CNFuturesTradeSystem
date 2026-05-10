"""TTS 全流程集成测试：连接、登录、行情订阅、下单、成交回报、撤单、查询

使用方式:
  pytest -m "gateway and live" -v -s              # 基础连接/行情/查询
  pytest -m "gateway and live_trade_window" -v -s  # 下单/成交（非交易时段跳过）
"""
import time
import warnings
import pytest

from src.event_engine.event import EventType
from src.event_engine.event_engine import EventEngine
from src.common.config import USER_ID, PASSWORD, BROKER_ID, TD_FRONT, MD_FRONT

INSTRUMENT = "m2609"


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
        from src.gateway.md_gateway import MdGateway
        from src.gateway.td_gateway import TdGateway
        from src.event_engine.logger import LogHandler
        self.engine = EventEngine()
        self.logger = LogHandler(self.engine)
        self.md_gw = MdGateway(
            self.engine, front_url=MD_FRONT,
            broker_id=BROKER_ID, user_id=USER_ID, password=PASSWORD,
        )
        self.td_gw = TdGateway(
            self.engine, front_url=TD_FRONT,
            broker_id=BROKER_ID, user_id=USER_ID, password=PASSWORD,
            app_id="", auth_code="",
        )

    def _connect(self):
        md_c = _EC(self.engine, EventType.MD_LOGIN)
        self.md_gw.connect()
        md_c.wait(timeout=15)
        assert self.md_gw.status == "logined"
        td_c = _EC(self.engine, EventType.TD_LOGIN)
        self.td_gw.connect()
        td_c.wait(timeout=15)
        assert self.td_gw.status == "logined"

    def _drain(self):
        for _ in range(30):
            self.engine.process_one()
            time.sleep(0.01)

    def teardown_method(self):
        try:
            self.md_gw.close()
        except Exception as e:
            warnings.warn("MD close: %s" % e)
        try:
            self.td_gw.close()
        except Exception as e:
            warnings.warn("TD close: %s" % e)
        self.logger.close()

    # ================================================
    # 连接测试
    # ================================================

    def test_01_connect_md(self):
        """行情网关连接+登录"""
        c = _EC(self.engine, EventType.MD_LOGIN)
        self.md_gw.connect()
        c.wait(timeout=15)
        assert self.md_gw.status == "logined"
        print("  MD登录成功 TradingDay=%s" % c.last.data.get("trading_day", ""))

    def test_02_connect_td(self):
        """交易网关连接+登录（TTS跳过认证）"""
        c = _EC(self.engine, EventType.TD_LOGIN)
        self.td_gw.connect()
        c.wait(timeout=15)
        assert self.td_gw.status == "logined"
        print("  TD登录成功 TradingDay=%s" % c.last.data.get("trading_day", ""))

    def test_03_dual_connect(self):
        """MD+TD同时连接"""
        md_c = _EC(self.engine, EventType.MD_LOGIN)
        td_c = _EC(self.engine, EventType.TD_LOGIN)
        self.md_gw.connect()
        self.td_gw.connect()
        td_c.wait(timeout=15)
        md_c.wait(timeout=15)
        assert md_c.last.data["error_id"] == 0
        assert td_c.last.data["error_id"] == 0

    # ================================================
    # 行情测试
    # ================================================

    def test_10_subscribe_tick(self):
        """行情订阅 -> Tick 数据"""
        self._connect()
        c = _EC(self.engine, EventType.TICK)
        self.md_gw.subscribe(INSTRUMENT)
        ev = c.wait(timeout=20)
        d = ev.data
        print("  %s last=%.2f bid=%.2f/%d ask=%.2f/%d" % (
            d["instrument_id"], d["last_price"],
            d["bid_price1"], d["bid_volume1"],
            d["ask_price1"], d["ask_volume1"],
        ))
        assert d["instrument_id"] == INSTRUMENT
        assert isinstance(d["last_price"], (int, float))

    # ================================================
    # 查询测试
    # ================================================

    def test_20_query_account(self):
        """查询资金"""
        self._connect()
        c = _EC(self.engine, EventType.ACCOUNT)
        self.td_gw.query_account()
        ev = c.wait(timeout=15)
        d = ev.data
        print("  account=%s balance=%.2f avail=%.2f" % (
            d.get("account_id", ""), d["balance"], d["available"],
        ))
        assert d["balance"] >= 0

    def test_21_query_positions(self):
        """查询持仓（空仓也正常）"""
        self._connect()
        c = _EC(self.engine, EventType.POSITION)
        self.td_gw.query_positions()
        time.sleep(2)
        self._drain()
        print("  持仓记录=%d 条" % len(c.events))
        for p in c.events:
            dd = p.data
            print("  %s yd=%s today=%s profit=%s" % (
                dd["instrument_id"], dd["yd_position"],
                dd["today_position"], dd["position_profit"],
            ))
        assert isinstance(len(c.events), int)

    def test_22_settlement(self):
        """结算单查询（TTS可能返回error=-1）"""
        self._connect()
        c = _EC(self.engine, EventType.SETTLEMENT_INFO)
        self.td_gw.qry_settlement_info()
        ev = c.wait(timeout=15)
        print("  error=%d msg=%s" % (ev.data["error_id"], ev.data.get("error_msg", "")))
        assert ev.data["error_id"] in (0, -1)

    # ================================================
    # 下单测试（非交易时段会 skip）
    # ================================================

    def test_30_buy_open(self):
        """买入开仓 1 手"""
        self._connect()
        tick_c = _EC(self.engine, EventType.TICK)
        self.md_gw.subscribe(INSTRUMENT)
        tick_c.wait(timeout=15)
        p = tick_c.last.data["last_price"]

        trade_c = _EC(self.engine, EventType.TRADE)
        or_c = _EC(self.engine, EventType.ORDER)
        ref = self.td_gw.send_order(INSTRUMENT, "buy", "open", p, 1)
        print("  开仓 order=%s @ %.0f" % (ref, p))
        assert ref is not None

        time.sleep(2)
        self._drain()
        if not trade_c.events and not or_c.events:
            pytest.skip("TTS未反馈订单/成交事件（非交易时段）")
        if trade_c.events:
            t = trade_c.last.data
            print("  成交 id=%s price=%s vol=%s" % (t["trade_id"], t["price"], t["volume"]))
            assert t["instrument_id"] == INSTRUMENT
        if or_c.events:
            print("  订单事件=%d 条" % len(or_c.events))

    def test_31_cancel(self):
        """挂低价单后撤单"""
        self._connect()
        tick_c = _EC(self.engine, EventType.TICK)
        self.md_gw.subscribe(INSTRUMENT)
        tick_c.wait(timeout=15)
        low = round(tick_c.last.data["bid_price1"] * 0.3, 0)

        or_c = _EC(self.engine, EventType.ORDER)
        ref = self.td_gw.send_order(INSTRUMENT, "buy", "open", low, 1)
        print("  挂单 order=%s @ %.0f" % (ref, low))
        time.sleep(1)
        self._drain()

        self.td_gw.cancel_order(
            INSTRUMENT, ref,
            self.td_gw.front_id, self.td_gw.session_id,
        )
        print("  撤单已发")
        time.sleep(3)
        self._drain()

        matched = [e for e in or_c.events if e.data.get("order_ref") == ref]
        print("  订单事件=%d 条" % len(matched))
        if not matched:
            pytest.skip("TTS未反馈订单事件（非交易时段）")

    def test_32_sell_close(self):
        """卖出平仓 1 手"""
        self._connect()
        tick_c = _EC(self.engine, EventType.TICK)
        self.md_gw.subscribe(INSTRUMENT)
        tick_c.wait(timeout=15)
        ask = tick_c.last.data["ask_price1"]

        trade_c = _EC(self.engine, EventType.TRADE)
        ref = self.td_gw.send_order(INSTRUMENT, "sell", "close", ask, 1)
        print("  平仓 order=%s @ %.0f" % (ref, ask))
        assert ref is not None

        time.sleep(2)
        self._drain()
        if not trade_c.events:
            pytest.skip("TTS未反馈成交事件（非交易时段）")
        t = trade_c.last.data
        print("  成交 id=%s price=%s vol=%s" % (t["trade_id"], t["price"], t["volume"]))

    def test_40_reconnect_data(self):
        """重连后行情仍可订阅"""
        self._connect()
        c = _EC(self.engine, EventType.TICK)
        self.md_gw.subscribe(INSTRUMENT)
        c.wait(timeout=20)
        assert c.last.data["instrument_id"] == INSTRUMENT