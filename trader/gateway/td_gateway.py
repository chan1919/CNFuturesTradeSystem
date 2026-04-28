from trader.gateway.base import BaseGateway, GatewayStatus
from trader.event import Event, EventType
from openctp_ctp import tdapi
from pathlib import Path
import sys
import time


# 方向/开平常量映射
DIRECTION_BUY = "0"
DIRECTION_SELL = "1"
OFFSET_OPEN = "0"
OFFSET_CLOSE = "1"
OFFSET_CLOSE_TODAY = "3"
OFFSET_CLOSE_YESTERDAY = "4"
HEDGE_SPECULATION = "1"
PRICE_TYPE_LIMIT = "2"


class TdGateway(BaseGateway):
    def __init__(self, event_engine, front_url="", broker_id="", user_id="", password="",
                 app_id="", auth_code=""):
        super().__init__()
        self._event_engine = event_engine
        self._front_url = front_url
        self._broker_id = broker_id
        self._user_id = user_id
        self._password = password
        self._app_id = app_id
        self._auth_code = auth_code
        self._api = None
        self._spi = None
        self.front_id = 0
        self.session_id = 0
        self._order_ref = 0
        self._investor_id = ""
        self._settlement_confirmed = False
        self._auth_timeout_seconds = 30.0
        self._auth_started_at = None
        self._auth_pending = False

    def connect(self, front_url=None):
        if front_url:
            self._front_url = front_url
        self.status = GatewayStatus.CONNECTING
        self._settlement_confirmed = False
        self._auth_started_at = None
        self._auth_pending = False
        flow_dir = Path(__file__).resolve().parent.parent.parent / "flow"
        flow_dir.mkdir(parents=True, exist_ok=True)
        self._api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi(f"{flow_dir}/")
        self._spi = _TdSpiProxy(self._api, self._event_engine, self)
        self._api.RegisterSpi(self._spi)
        self._api.RegisterFront(self._front_url)
        self._api.SubscribePrivateTopic(tdapi.THOST_TERT_RESUME)
        self._api.SubscribePublicTopic(tdapi.THOST_TERT_RESUME)
        self._api.Init()

    def login(self):
        if not (self._broker_id and self._user_id and self._password):
            return
        req = tdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = self._broker_id
        req.UserID = self._user_id
        req.Password = self._password
        self._api.ReqUserLogin(req, 0)

    # TODO: add auth timeout mechanism — authenticate() should handle timeout
    def authenticate(self):
        if not (self._broker_id and self._user_id and self._auth_code and self._app_id):
            return False
        self._auth_started_at = time.monotonic()
        self._auth_pending = True
        req = tdapi.CThostFtdcReqAuthenticateField()
        req.BrokerID = self._broker_id
        req.UserID = self._user_id
        req.AppID = self._app_id
        req.AuthCode = self._auth_code
        self._api.ReqAuthenticate(req, 0)
        return True

    def check_timeouts(self, now=None):
        if not self._auth_pending or self._auth_started_at is None:
            return False

        elapsed = (time.monotonic() - self._auth_started_at) if now is None else now
        if elapsed < self._auth_timeout_seconds:
            return False

        self._auth_pending = False
        self._auth_started_at = None
        self._event_engine.put(Event(EventType.TD_AUTHENTICATE, data={
            "error_id": -1,
            "error_msg": "authenticate timeout",
            "user_id": self._user_id,
            "app_id": self._app_id,
            "log_level": "error",
        }))
        self.login()
        return True

    def _next_order_ref(self):
        self._order_ref += 1
        return str(self._order_ref)

    def send_order(self, instrument_id, direction, offset_flag, price, volume):
        if self.status != GatewayStatus.LOGINED:
            raise RuntimeError("TdGateway: not logined, cannot send order")

        direction_byte = DIRECTION_BUY if direction == "buy" else DIRECTION_SELL
        offset_map = {
            "open": OFFSET_OPEN,
            "close": OFFSET_CLOSE,
            "close_today": OFFSET_CLOSE_TODAY,
            "close_yesterday": OFFSET_CLOSE_YESTERDAY,
        }
        offset_byte = offset_map.get(offset_flag, OFFSET_OPEN)

        req = tdapi.CThostFtdcInputOrderField()
        req.BrokerID = self._broker_id
        req.InvestorID = self._investor_id or self._user_id
        req.InstrumentID = instrument_id
        req.OrderRef = self._next_order_ref()
        req.UserID = self._user_id
        req.OrderPriceType = PRICE_TYPE_LIMIT
        req.Direction = direction_byte
        req.CombOffsetFlag = offset_byte
        req.CombHedgeFlag = HEDGE_SPECULATION
        req.LimitPrice = price
        req.VolumeTotalOriginal = volume
        req.TimeCondition = "3"
        req.VolumeCondition = "1"
        req.MinVolume = 1
        req.ContingentCondition = "1"
        req.StopPrice = 0
        req.ForceCloseReason = "0"
        req.IsAutoSuspend = 0
        req.UserForceClose = 0

        self._api.ReqOrderInsert(req, 0)
        return req.OrderRef

    def cancel_order(self, instrument_id, order_ref, front_id, session_id, order_sys_id=""):
        if self.status != GatewayStatus.LOGINED:
            raise RuntimeError("TdGateway: not logined, cannot cancel order")

        req = tdapi.CThostFtdcInputOrderActionField()
        req.BrokerID = self._broker_id
        req.InvestorID = self._investor_id or self._user_id
        req.InstrumentID = instrument_id
        req.OrderRef = order_ref
        req.FrontID = front_id
        req.SessionID = session_id
        req.OrderSysID = order_sys_id
        req.ActionFlag = "0"

        self._api.ReqOrderAction(req, 0)

    def qry_settlement_info(self, trading_day=""):
        if self.status != GatewayStatus.LOGINED:
            raise RuntimeError("TdGateway: not logined, cannot query settlement")
        req = tdapi.CThostFtdcQrySettlementInfoField()
        req.BrokerID = self._broker_id
        req.InvestorID = self._investor_id or self._user_id
        req.TradingDay = trading_day
        self._api.ReqQrySettlementInfo(req, 0)

    def settlement_info_confirm(self):
        if self.status != GatewayStatus.LOGINED:
            raise RuntimeError("TdGateway: not logined, cannot confirm settlement")
        req = tdapi.CThostFtdcSettlementInfoConfirmField()
        req.BrokerID = self._broker_id
        req.InvestorID = self._investor_id or self._user_id
        self._api.ReqSettlementInfoConfirm(req, 0)

    def query_positions(self):
        if self.status != GatewayStatus.LOGINED:
            raise RuntimeError("TdGateway: not logined, cannot query")
        req = tdapi.CThostFtdcQryInvestorPositionField()
        req.BrokerID = self._broker_id
        req.InvestorID = self._investor_id or self._user_id
        self._api.ReqQryInvestorPosition(req, 0)

    def query_account(self):
        if self.status != GatewayStatus.LOGINED:
            raise RuntimeError("TdGateway: not logined, cannot query")
        req = tdapi.CThostFtdcQryTradingAccountField()
        req.BrokerID = self._broker_id
        req.InvestorID = self._investor_id or self._user_id
        self._api.ReqQryTradingAccount(req, 0)

    def close(self):
        if self._api:
            self._api.Release()
            self._api = None
        self.status = GatewayStatus.DISCONNECTED
        self._settlement_confirmed = False
        self._auth_started_at = None
        self._auth_pending = False


class _TdSpiProxy(tdapi.CThostFtdcTraderSpi):
    def __init__(self, api, event_engine, gateway):
        super().__init__()
        self._api = api
        self._ee = event_engine
        self._gw = gateway

    def OnFrontConnected(self):
        self._gw.status = GatewayStatus.CONNECTED
        self._ee.put(Event(EventType.TD_CONNECTED, data={"log_level": "info"}))
        if not self._gw.authenticate():
            self._gw.login()

    def OnFrontDisconnected(self, nReason):
        self._gw.status = GatewayStatus.DISCONNECTED
        self._ee.put(Event(EventType.TD_DISCONNECTED, data={
            "reason": nReason,
            "log_level": "warning",
        }))

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID == 0:
            self._gw.status = GatewayStatus.LOGINED
            self._gw.front_id = pRspUserLogin.FrontID
            self._gw.session_id = pRspUserLogin.SessionID
            if pRspUserLogin.MaxOrderRef:
                self._gw._order_ref = int(pRspUserLogin.MaxOrderRef)
        error_id = pRspInfo.ErrorID if pRspInfo else -1
        error_msg = pRspInfo.ErrorMsg if pRspInfo else ""
        log_level = "info" if error_id == 0 else "error"
        self._ee.put(Event(EventType.TD_LOGIN, data={
            "error_id": error_id,
            "error_msg": error_msg,
            "trading_day": pRspUserLogin.TradingDay,
            "front_id": pRspUserLogin.FrontID,
            "session_id": pRspUserLogin.SessionID,
            "log_level": log_level,
        }))

    # TODO: add auth timeout mechanism — OnRspAuthenticate may never return
    def OnRspAuthenticate(self, pRspAuthenticate, pRspInfo, nRequestID, bIsLast):
        self._gw._auth_pending = False
        self._gw._auth_started_at = None
        error_id = pRspInfo.ErrorID if pRspInfo else -1
        error_msg = pRspInfo.ErrorMsg if pRspInfo else ""
        log_level = "info" if error_id == 0 else "error"
        self._ee.put(Event(EventType.TD_AUTHENTICATE, data={
            "error_id": error_id,
            "error_msg": error_msg,
            "user_id": pRspAuthenticate.UserID if pRspAuthenticate else self._gw._user_id,
            "app_id": pRspAuthenticate.AppID if pRspAuthenticate else self._gw._app_id,
            "log_level": log_level,
        }))
        if error_id == 0:
            self._gw.login()

    def OnRtnOrder(self, pOrder):
        self._ee.put(Event(EventType.ORDER, data={
            "instrument_id": pOrder.InstrumentID,
            "order_ref": pOrder.OrderRef,
            "order_sys_id": pOrder.OrderSysID,
            "direction": pOrder.Direction,
            "offset_flag": pOrder.CombOffsetFlag,
            "order_status": pOrder.OrderStatus,
            "volume_total_original": pOrder.VolumeTotalOriginal,
            "volume_traded": pOrder.VolumeTraded,
            "volume_total": pOrder.VolumeTotal,
            "limit_price": pOrder.LimitPrice,
            "front_id": pOrder.FrontID,
            "session_id": pOrder.SessionID,
            "insert_date": pOrder.InsertDate,
            "insert_time": pOrder.InsertTime,
            "cancel_time": pOrder.CancelTime,
            "status_msg": pOrder.StatusMsg,
            "log_level": "info",
        }))

    def OnRtnTrade(self, pTrade):
        self._ee.put(Event(EventType.TRADE, data={
            "instrument_id": pTrade.InstrumentID,
            "trade_id": pTrade.TradeID,
            "order_ref": pTrade.OrderRef,
            "order_sys_id": pTrade.OrderSysID,
            "direction": pTrade.Direction,
            "offset_flag": pTrade.OffsetFlag,
            "price": pTrade.Price,
            "volume": pTrade.Volume,
            "trade_date": pTrade.TradeDate,
            "trade_time": pTrade.TradeTime,
            "log_level": "info",
        }))

    def OnRspQryInvestorPosition(self, pInvestorPosition, pRspInfo, nRequestID, bIsLast):
        if pInvestorPosition:
            self._ee.put(Event(EventType.POSITION, data={
                "instrument_id": pInvestorPosition.InstrumentID,
                "posi_direction": pInvestorPosition.PosiDirection,
                "position_date": pInvestorPosition.PositionDate,
                "yd_position": pInvestorPosition.YdPosition,
                "today_position": pInvestorPosition.TodayPosition,
                "position_profit": pInvestorPosition.PositionProfit,
                "use_margin": pInvestorPosition.UseMargin,
                "frozen": pInvestorPosition.LongFrozen if hasattr(pInvestorPosition, "LongFrozen") else 0,
                "log_level": "info",
            }))

    def OnRspQryTradingAccount(self, pTradingAccount, pRspInfo, nRequestID, bIsLast):
        if pTradingAccount:
            self._ee.put(Event(EventType.ACCOUNT, data={
                "account_id": pTradingAccount.AccountID,
                "pre_balance": pTradingAccount.PreBalance,
                "balance": pTradingAccount.Balance,
                "available": pTradingAccount.Available,
                "curr_margin": pTradingAccount.CurrMargin,
                "frozen_margin": pTradingAccount.FrozenMargin,
                "frozen_cash": pTradingAccount.FrozenCash,
                "position_profit": pTradingAccount.PositionProfit,
                "commission": pTradingAccount.Commission,
                "log_level": "info",
            }))

    def OnRspQrySettlementInfo(self, pSettlementInfo, pRspInfo, nRequestID, bIsLast):
        error_id = pRspInfo.ErrorID if pRspInfo else -1
        error_msg = pRspInfo.ErrorMsg if pRspInfo else ""
        log_level = "info" if error_id == 0 else "error"
        data = {
            "error_id": error_id,
            "error_msg": error_msg,
            "log_level": log_level,
            "is_last": bIsLast,
        }
        if pSettlementInfo:
            data.update({
                "trading_day": pSettlementInfo.TradingDay,
                "content": pSettlementInfo.Content,
                "sequence_no": pSettlementInfo.SequenceNo,
            })
        self._ee.put(Event(EventType.SETTLEMENT_INFO, data=data))
        if bIsLast and error_id == 0 and not getattr(self._gw, "_settlement_confirmed", False):
            self._gw.settlement_info_confirm()

    def OnRspSettlementInfoConfirm(self, pSettlementInfoConfirm, pRspInfo, nRequestID, bIsLast):
        error_id = pRspInfo.ErrorID if pRspInfo else -1
        error_msg = pRspInfo.ErrorMsg if pRspInfo else ""
        log_level = "info" if error_id == 0 else "error"
        data = {
            "error_id": error_id,
            "error_msg": error_msg,
            "log_level": log_level,
            "is_last": bIsLast,
        }
        if pSettlementInfoConfirm:
            data.update({
                "trading_day": pSettlementInfoConfirm.TradingDay,
                "confirm_time": pSettlementInfoConfirm.ConfirmTime,
                "confirm_date": pSettlementInfoConfirm.ConfirmDate,
            })
            if error_id == 0:
                self._gw._settlement_confirmed = True
        self._ee.put(Event(EventType.SETTLEMENT_INFO_CONFIRMED, data=data))

    # TODO: add auth timeout mechanism — authenticate() should handle timeout
    def OnRspError(self, pRspInfo, nRequestID, bIsLast):
        error_id = pRspInfo.ErrorID if pRspInfo else -1
        error_msg = pRspInfo.ErrorMsg if pRspInfo else ""
        print(f"[CTP Error][Td] nRequestID={nRequestID}, ErrorID={error_id}, Msg={error_msg}", file=sys.stderr)
        self._ee.put(Event(EventType.SYSTEM, data={
            "error_id": error_id,
            "error_msg": error_msg,
            "request_id": nRequestID,
            "log_level": "error",
            "source": "TdGateway.OnRspError",
        }))
