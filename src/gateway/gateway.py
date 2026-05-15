from src.common.account import Account
from src.common.contract import Contract
from src.event_bus.event import EventType
from src.gateway.md_gateway import MdGateway
from src.gateway.td_gateway import TdGateway


class Gateway:
    """统一网关 Facade，封装 MdGateway + TdGateway + Account + 合约缓存

    对外提供 connect/subscribe/send_order/query 等统一接口，
    内部订阅 TICK/TRADE/POSITION 事件自动维护 Account 状态。
    MdGateway / TdGateway 可通过 .md / .td 属性访问（集成测试用）。
    """

    def __init__(self, event_bus, md_front_url="", td_front_url="",
                 broker_id="", user_id="", password="",
                 app_id="", auth_code=""):
        self._event_bus = event_bus
        self._md = MdGateway(event_bus, md_front_url, broker_id, user_id, password)
        self._td = TdGateway(event_bus, td_front_url, broker_id, user_id, password, app_id, auth_code)
        self.account = Account()
        self._contracts: dict[str, Contract] = {}

        event_bus.register(EventType.TICK, self._on_tick)
        event_bus.register(EventType.TRADE, self._on_trade)
        event_bus.register(EventType.POSITION, self._on_position)
        event_bus.register(EventType.ACCOUNT, self._on_account)

    def connect(self):
        self._md.connect()
        self._td.connect()

    def close(self):
        self._md.close()
        self._td.close()

    def subscribe(self, instruments):
        self._md.subscribe(instruments)

    def send_order(self, instrument_id, direction, offset, price, volume):
        return self._td.send_order(instrument_id, direction, offset, price, volume)

    def cancel_order(self, instrument_id, order_ref, front_id, session_id, order_sys_id=""):
        self._td.cancel_order(instrument_id, order_ref, front_id, session_id, order_sys_id)

    def query_positions(self):
        self._td.query_positions()

    def query_account_info(self):
        self._td.query_account()

    def query_instruments(self):
        self._td.query_instruments()

    def qry_settlement_info(self, trading_day=""):
        self._td.qry_settlement_info(trading_day)

    def settlement_info_confirm(self):
        self._td.settlement_info_confirm()

    def add_contract(self, contract: Contract):
        """注册合约到缓存，用于成交/持仓事件还原 Position"""
        self._contracts[contract.instrument_id] = contract

    def get_contract(self, instrument_id: str) -> Contract | None:
        return self._contracts.get(instrument_id)

    @property
    def contracts(self) -> dict[str, Contract]:
        return dict(self._contracts)

    @property
    def md(self) -> MdGateway:
        return self._md

    @property
    def td(self) -> TdGateway:
        return self._td

    # ── 内部事件处理（自动维护 Account） ──

    def _on_tick(self, event):
        tick = event.data
        iid = tick.get("instrument_id", "")
        pos = self.account.get_position(iid)
        if pos:
            pos.update_last_price(tick.get("last_price", 0))

    def _on_trade(self, event):
        trade = event.data
        iid = trade.get("instrument_id", "")
        contract = self._contracts.get(iid)
        if contract:
            self.account.apply_trade(
                contract=contract,
                direction=trade.get("direction", ""),
                offset=trade.get("offset_flag", ""),
                volume=trade.get("volume", 0),
                price=float(trade.get("price", 0)),
            )

    def _on_account(self, event):
        self.account.update_from_query(event.data)

    def _on_position(self, event):
        data = event.data
        iid = data.get("instrument_id", "")
        contract = self._contracts.get(iid)
        self.account.update_from_ctp(
            instrument_id=iid,
            contract=contract,
            direction=data.get("direction", ""),
            yd=data.get("yd_position", 0),
            today=data.get("today_position", 0),
            frozen=data.get("frozen", 0),
        )