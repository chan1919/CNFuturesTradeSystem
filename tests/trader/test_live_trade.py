"""实盘集成测试：完整测试 CTP 连接、认证、登录、行情订阅、下单、查持仓/资金等核心交易流程
使用方式: pytest -m live -v -s
"""
import os
import time
import pytest
from dotenv import load_dotenv

from trader.engine import EventEngine
from trader.event import EventType
from trader.gateway.md_gateway import MdGateway
from trader.gateway.td_gateway import TdGateway
from trader.logger import LogHandler

load_dotenv(".env.local")


def get_config():
    return {
        "user_id": os.environ["CTP_USER_ID"],
        "password": os.environ["CTP_PASSWORD"],
        "broker_id": os.environ["CTP_BROKER_ID"],
        "td_front": os.environ["CTP_TD_FRONT"],
        "md_front": os.environ["CTP_MD_FRONT"],
        "app_id": os.environ["CTP_APP_ID"],
        "auth_code": os.environ["CTP_AUTH_CODE"],
    }


INSTRUMENT = "m2609"


class EventCollector:
    def __init__(self, engine, event_type):
        self.events = []
        engine.register(event_type, self._on_event)

    def _on_event(self, event):
        self.events.append(event)

    @property
    def last(self):
        return self.events[-1] if self.events else None

    def wait(self, engine, timeout=30, min_events=1):
        deadline = time.time() + timeout
        while time.time() < deadline:
            engine.process_one()
            if len(self.events) >= min_events:
                return self.events[-1]
            time.sleep(0.01)
        pytest.fail(f"等待事件超时 {timeout}s, 已收到 {len(self.events)} 个")


@pytest.mark.live
class TestLiveTrade:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.cfg = get_config()
        self.engine = EventEngine()
        self.logger = LogHandler(self.engine)
        self.md_gw = MdGateway(
            self.engine,
            front_url=self.cfg["md_front"],
            broker_id=self.cfg["broker_id"],
            user_id=self.cfg["user_id"],
            password=self.cfg["password"],
        )
        self.td_gw = TdGateway(
            self.engine,
            front_url=self.cfg["td_front"],
            broker_id=self.cfg["broker_id"],
            user_id=self.cfg["user_id"],
            password=self.cfg["password"],
            app_id=self.cfg["app_id"],
            auth_code=self.cfg["auth_code"],
        )

    def _drain_events(self):
        for _ in range(20):
            self.engine.process_one()

    def _connect_td(self):
        td_login = EventCollector(self.engine, EventType.TD_LOGIN)
        self.td_gw.connect()
        td_login.wait(self.engine, timeout=30)
        d = td_login.last.data
        if d["error_id"] != 0:
            pytest.fail(f"交易登录失败: {d.get('error_msg', '')}")
        return d

    def _connect_md(self):
        md_login = EventCollector(self.engine, EventType.MD_LOGIN)
        self.md_gw.connect()
        md_login.wait(self.engine, timeout=15)
        d = md_login.last.data
        if d["error_id"] != 0:
            pytest.fail(f"行情登录失败: {d.get('error_msg', '')}")
        return d

    def test_01_connect_and_login(self):
        md_login = EventCollector(self.engine, EventType.MD_LOGIN)
        td_login = EventCollector(self.engine, EventType.TD_LOGIN)
        td_auth = EventCollector(self.engine, EventType.TD_AUTHENTICATE)

        self.md_gw.connect()
        self.td_gw.connect()

        td_auth.wait(self.engine, timeout=15)
        td_login.wait(self.engine, timeout=15)
        md_login.wait(self.engine, timeout=15)

        assert td_auth.last.data["error_id"] == 0, \
            f"认证失败: {td_auth.last.data.get('error_msg', '')}"
        assert td_login.last.data["error_id"] == 0, \
            f"交易登录失败: {td_login.last.data.get('error_msg', '')}"
        assert md_login.last.data["error_id"] == 0, \
            f"行情登录失败: {md_login.last.data.get('error_msg', '')}"
        assert self.td_gw.status == "logined"
        assert self.md_gw.status == "logined"

        print(f"\n[OK] 交易认证成功")
        print(f"[OK] 交易登录成功, TradingDay={td_login.last.data.get('trading_day', '')}")
        print(f"[OK] 行情登录成功, TradingDay={md_login.last.data.get('trading_day', '')}")

    def test_02_query_account(self):
        self._connect_td()

        account = EventCollector(self.engine, EventType.ACCOUNT)
        self.td_gw.query_account()
        account.wait(self.engine, timeout=15)

        d = account.last.data
        print(f"\n[账户资金] 账号={d.get('account_id', '')}, "
              f"余额={d.get('balance', 0):.2f}, "
              f"可用={d.get('available', 0):.2f}, "
              f"持仓盈亏={d.get('position_profit', 0):.2f}, "
              f"保证金={d.get('curr_margin', 0):.2f}")

    def test_03_query_positions(self):
        self._connect_td()

        positions = EventCollector(self.engine, EventType.POSITION)
        self.td_gw.query_positions()
        time.sleep(2)
        self._drain_events()

        print(f"\n[持仓] 收到 {len(positions.events)} 条持仓记录")
        for p in positions.events:
            print(f"  合约={p.data['instrument_id']}, "
                  f"多空={'多' if p.data['posi_direction']=='2' else '空'}, "
                  f"昨仓={p.data['yd_position']}, 今仓={p.data['today_position']}")

    def test_04_subscribe_tick(self):
        self._connect_md()

        tick = EventCollector(self.engine, EventType.TICK)
        self.md_gw.subscribe(INSTRUMENT)
        tick.wait(self.engine, timeout=15)

        d = tick.last.data
        print(f"\n[Tick] {d['instrument_id']} 最新价={d['last_price']}, "
              f"买一={d['bid_price1']}/{d['bid_volume1']}, "
              f"卖一={d['ask_price1']}/{d['ask_volume1']}, "
              f"成交量={d['volume']}, 时间={d['update_time']}")

    def test_05_open_long_and_close(self):
        self._connect_td()
        self._connect_md()

        tick = EventCollector(self.engine, EventType.TICK)
        self.md_gw.subscribe(INSTRUMENT)
        tick.wait(self.engine, timeout=15)
        price = tick.last.data["last_price"]
        ask_price = tick.last.data["ask_price1"]

        trade = EventCollector(self.engine, EventType.TRADE)

        print(f"\n[开仓] {INSTRUMENT} 买入开仓 1手, 限价 {price} (卖一价={ask_price})")
        order_ref = self.td_gw.send_order(
            instrument_id=INSTRUMENT,
            direction="buy",
            offset_flag="open",
            price=price,
            volume=1,
        )
        print(f"  订单编号: {order_ref}")

        trade.wait(self.engine, timeout=30)
        t = trade.last.data
        print(f"  [成交] ID={t['trade_id']}, 价格={t['price']}, 数量={t['volume']}, "
              f"方向={'买' if t['direction']=='0' else '卖'}, "
              f"开平={'开' if t['offset_flag']=='0' else '平'}")

        time.sleep(1)
        self._drain_events()

        # Get latest tick for close price
        self.md_gw.subscribe(INSTRUMENT)
        tick.wait(self.engine, timeout=15, min_events=2)
        bid_price = tick.last.data["bid_price1"]
        print(f"\n[平仓] {INSTRUMENT} 卖出平仓 1手, 限价 {bid_price} (买一价={bid_price})")
        order_ref2 = self.td_gw.send_order(
            instrument_id=INSTRUMENT,
            direction="sell",
            offset_flag="close",
            price=bid_price,
            volume=1,
        )
        print(f"  订单编号: {order_ref2}")

        trade.wait(self.engine, timeout=30, min_events=2)
        t2 = trade.last.data
        print(f"  [成交] ID={t2['trade_id']}, 价格={t2['price']}, 数量={t2['volume']}, "
              f"方向={'买' if t2['direction']=='0' else '卖'}, "
              f"开平={'开' if t2['offset_flag']=='0' else '平'}")

        time.sleep(1)
        self._drain_events()

        print(f"\n[验证] 再次查询持仓和资金...")
        positions = EventCollector(self.engine, EventType.POSITION)
        self.td_gw.query_positions()
        time.sleep(2)
        self._drain_events()

        pos_target = [p for p in positions.events if p.data["instrument_id"] == INSTRUMENT]
        if pos_target:
            for p in pos_target:
                yd = p.data["yd_position"]
                td = p.data["today_position"]
                print(f"  剩余持仓: 昨仓={yd}, 今仓={td}")
        else:
            print(f"  无 {INSTRUMENT} 持仓 (已全部平仓)")

        account = EventCollector(self.engine, EventType.ACCOUNT)
        self.td_gw.query_account()
        time.sleep(1)
        self._drain_events()

        if account.events:
            d = account.last.data
            print(f"  资金: 余额={d.get('balance', 0):.2f}, 可用={d.get('available', 0):.2f}")

    def test_06_settlement_confirm(self):
        self._connect_td()

        settlement_info = EventCollector(self.engine, EventType.SETTLEMENT_INFO)
        settlement_confirm = EventCollector(self.engine, EventType.SETTLEMENT_INFO_CONFIRMED)

        print("\n[结算单查询] 发送 QrySettlementInfo...")
        self.td_gw.qry_settlement_info()

        info_event = settlement_info.wait(self.engine, timeout=15)
        d = info_event.data
        print(f"  error_id={d['error_id']}, error_msg={d.get('error_msg', '')}")
        if d["error_id"] == 0:
            content = d.get("content", "")
            print(f"  结算单内容({len(content)}字符), trading_day={d.get('trading_day', '')}")
            if content:
                print(f"  前200字: {content[:200]}")

        confirm_event = settlement_confirm.wait(self.engine, timeout=15)
        d2 = confirm_event.data
        print(f"\n[结算单确认] error_id={d2['error_id']}, error_msg={d2.get('error_msg', '')}")
        assert d2["error_id"] == 0, \
            f"结算单确认失败: {d2.get('error_msg', '')}"
        print(f"  确认日期={d2.get('confirm_date', '')}, 确认时间={d2.get('confirm_time', '')}")
        print(f"  FrontID={self.td_gw.front_id}, SessionID={self.td_gw.session_id}")

    def test_07_cancel_order(self):
        self._connect_td()
        self._connect_md()

        tick = EventCollector(self.engine, EventType.TICK)
        self.md_gw.subscribe(INSTRUMENT)
        tick.wait(self.engine, timeout=15)
        low_price = round(tick.last.data["bid_price1"] * 0.5, 0)

        orders = EventCollector(self.engine, EventType.ORDER)

        print(f"\n[撤单测试] {INSTRUMENT} 低挂买开 1手 @ {low_price}")
        order_ref = self.td_gw.send_order(
            instrument_id=INSTRUMENT,
            direction="buy",
            offset_flag="open",
            price=low_price,
            volume=1,
        )
        print(f"  订单编号: {order_ref}")

        time.sleep(1)
        self._drain_events()

        print(f"\n[撤单] 撤消订单 {order_ref}")
        self.td_gw.cancel_order(
            instrument_id=INSTRUMENT,
            order_ref=order_ref,
            front_id=self.td_gw.front_id,
            session_id=self.td_gw.session_id,
        )

        time.sleep(3)
        self._drain_events()

        cancelled = [
            e for e in orders.events
            if e.data.get("order_ref") == order_ref
        ]
        assert cancelled, "未收到该订单的任何 ORDER 事件"

        last_order = cancelled[-1].data
        status = last_order.get("order_status", "")
        print(f"  订单状态码: {status}")
        print(f"  状态消息: {last_order.get('status_msg', '')}")

        assert status in ("5",), f"预期撤单状态 '5', 实际 '{status}'"

    def teardown_method(self):
        self._cleanup_positions()
        self.md_gw.close()
        self.td_gw.close()
        self.logger.close()

    def _cleanup_positions(self):
        if self.td_gw.status != "logined":
            return
        positions = EventCollector(self.engine, EventType.POSITION)
        self.td_gw.query_positions()
        time.sleep(2)
        self._drain_events()

        for p in positions.events:
            inst = p.data["instrument_id"]
            direction = p.data["posi_direction"]
            yd = p.data["yd_position"]
            today = p.data["today_position"]
            total = yd + today
            if total <= 0:
                continue

            close_dir = "sell" if direction == "2" else "buy"

            # Connect MD for price if needed
            if self.md_gw.status not in ("connected", "logined"):
                self._connect_md()
            tick = EventCollector(self.engine, EventType.TICK)
            self.md_gw.subscribe(inst)
            try:
                tick.wait(self.engine, timeout=10)
            except Exception:
                continue

            if not tick.events:
                continue
            t = tick.last.data
            close_price = t["bid_price1"] if close_dir == "sell" else t["ask_price1"]

            # Try close first, then close_today
            trade = EventCollector(self.engine, EventType.TRADE)
            try:
                self.td_gw.send_order(inst, close_dir, "close", close_price, total)
            except RuntimeError:
                pass
            time.sleep(3)
            self._drain_events()

            if not trade.events:
                try:
                    self.td_gw.send_order(inst, close_dir, "close_today", close_price, total)
                except RuntimeError:
                    pass
                time.sleep(3)
                self._drain_events()

            print(f"  [清理] 平仓 {inst} {'多' if direction=='2' else '空'} {total}手 @ {close_price}")
