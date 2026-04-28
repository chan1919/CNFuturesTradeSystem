from trader.gateway.base import BaseGateway, GatewayStatus
from trader.event import Event, EventType
from openctp_ctp import mdapi
from pathlib import Path


class MdGateway(BaseGateway):
    def __init__(self, event_engine, front_url="", broker_id="", user_id="", password=""):
        super().__init__()
        self._event_engine = event_engine
        self._front_url = front_url
        self._broker_id = broker_id
        self._user_id = user_id
        self._password = password
        self._api = None
        self._spi = None

    def connect(self, front_url=None):
        if front_url:
            self._front_url = front_url
        self.status = GatewayStatus.CONNECTING
        flow_dir = Path(__file__).resolve().parent.parent.parent / "flow"
        flow_dir.mkdir(parents=True, exist_ok=True)
        self._api = mdapi.CThostFtdcMdApi.CreateFtdcMdApi(f"{flow_dir}/")
        self._spi = _MdSpiProxy(self._api, self._event_engine, self)
        self._api.RegisterSpi(self._spi)
        self._api.RegisterFront(self._front_url)
        self._api.Init()

    def login(self):
        if not (self._broker_id and self._user_id and self._password):
            return
        req = mdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = self._broker_id
        req.UserID = self._user_id
        req.Password = self._password
        self._api.ReqUserLogin(req, 0)

    def subscribe(self, instruments):
        if self.status in (GatewayStatus.DISCONNECTED, GatewayStatus.CONNECTING):
            raise RuntimeError("MdGateway: not connected, cannot subscribe")
        if isinstance(instruments, str):
            instruments = [instruments]
        instruments = [i.encode() if isinstance(i, str) else i for i in instruments]
        self._api.SubscribeMarketData(instruments, len(instruments))

    def close(self):
        if self._api:
            self._api.Release()
            self._api = None
        self.status = GatewayStatus.DISCONNECTED


class _MdSpiProxy(mdapi.CThostFtdcMdSpi):
    def __init__(self, api, event_engine, gateway):
        super().__init__()
        self._api = api
        self._ee = event_engine
        self._gw = gateway

    def OnFrontConnected(self):
        self._gw.status = GatewayStatus.CONNECTED
        self._ee.put(Event(EventType.MD_CONNECTED))
        self._gw.login()

    def OnFrontDisconnected(self, nReason):
        self._gw.status = GatewayStatus.DISCONNECTED
        self._ee.put(Event(EventType.MD_DISCONNECTED, data={"reason": nReason}))

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        if pRspInfo.ErrorID == 0:
            self._gw.status = GatewayStatus.LOGINED
        self._ee.put(Event(EventType.MD_LOGIN, data={
            "error_id": pRspInfo.ErrorID,
            "error_msg": pRspInfo.ErrorMsg,
            "trading_day": self._api.GetTradingDay(),
            "login_time": pRspUserLogin.LoginTime,
        }))

    def OnRtnDepthMarketData(self, pDepthMarketData):
        self._ee.put(Event(EventType.TICK, data={
            "instrument_id": pDepthMarketData.InstrumentID,
            "exchange_id": pDepthMarketData.ExchangeID,
            "last_price": pDepthMarketData.LastPrice,
            "volume": pDepthMarketData.Volume,
            "open_interest": pDepthMarketData.OpenInterest,
            "bid_price1": pDepthMarketData.BidPrice1,
            "bid_volume1": pDepthMarketData.BidVolume1,
            "ask_price1": pDepthMarketData.AskPrice1,
            "ask_volume1": pDepthMarketData.AskVolume1,
            "highest_price": pDepthMarketData.HighestPrice,
            "lowest_price": pDepthMarketData.LowestPrice,
            "open_price": pDepthMarketData.OpenPrice,
            "pre_close_price": pDepthMarketData.PreClosePrice,
            "upper_limit_price": pDepthMarketData.UpperLimitPrice,
            "lower_limit_price": pDepthMarketData.LowerLimitPrice,
            "update_time": pDepthMarketData.UpdateTime,
            "update_millisec": pDepthMarketData.UpdateMillisec,
            "trading_day": pDepthMarketData.TradingDay,
            "action_day": pDepthMarketData.ActionDay,
        }))

    def OnRspError(self, pRspInfo, nRequestID, bIsLast):
        pass