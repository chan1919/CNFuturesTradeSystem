"""TDD: MdGateway 的测试
我们要验证:
1. connect() → RegisterFront + Init 被调用
2. Spi 回调被转换成 Event 放入引擎
3. subscribe() 正确调用 SubscribeMarketData
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from trader.engine import EventEngine
from trader.event import Event, EventType


# ---- helpers ----

def make_mock_md_api():
    """创建一个模拟的 MdApi"""
    api = MagicMock()
    api.GetTradingDay.return_value = "20260426"
    return api


# ---- 测试 ----

class TestMdGatewayConnect:
    """测试连接相关"""

    def test_connect_calls_register_front_and_init(self):
        """connect() 应调用 RegisterFront 和 Init"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine, front_url="tcp://127.0.0.1:10100")

            gw.connect()

            md_api.RegisterFront.assert_called_once_with("tcp://127.0.0.1:10100")
            md_api.RegisterSpi.assert_called_once()
            md_api.Init.assert_called_once()

    def test_connect_changes_status(self):
        """connect() 后 status 应为 CONNECTING"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine, front_url="tcp://127.0.0.1:10100")

            gw.connect()
            assert gw.status == "connecting"


class TestMdGatewayCallbacks:
    """测试回调转事件"""

    def _connect_and_connected(self, gw, md_api):
        """Helper: connect + simulate OnFrontConnected → gateway reaches CONNECTED"""
        gw.connect()
        spi = md_api.RegisterSpi.call_args[0][0]
        spi.OnFrontConnected()
        return spi

    def test_on_front_connected_puts_event(self):
        """OnFrontConnected 回调应推送 EventType.MD_CONNECTED"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine, front_url="tcp://127.0.0.1:10100")
            gw.connect()

            spi = md_api.RegisterSpi.call_args[0][0]
            received = []
            engine.register(EventType.MD_CONNECTED, lambda e: received.append(e))

            # OnFrontConnected pushes EventType.MD_CONNECTED + calls login()
            # login() tries to create ReqUserLoginField from mock → fine
            spi.OnFrontConnected()
            engine.process_one()

            assert gw.status == "connected"
            assert len(received) == 1
            assert received[0].type == EventType.MD_CONNECTED

    def test_on_rsp_user_login_puts_event(self):
        """OnRspUserLogin 成功应推送 EventType.MD_LOGIN"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine, broker_id="9999", user_id="test", password="123")
            gw.connect()

            spi = md_api.RegisterSpi.call_args[0][0]
            received = []
            engine.register(EventType.MD_LOGIN, lambda e: received.append(e))

            # 必须先让 OnFrontConnected 触发
            spi.OnFrontConnected()
            engine.process_one()  # consume EventType.MD_CONNECTED

            rsp = MagicMock()
            rsp.CZCETime = "10:30:00"
            rsp.SHFETime = "10:30:00"
            rsp.DCETime = "10:30:00"
            rsp.FFEXTime = "10:30:00"
            rsp.INETime = "10:30:00"

            info = MagicMock()
            info.ErrorID = 0
            info.ErrorMsg = ""

            spi.OnRspUserLogin(rsp, info, 1, True)
            engine.process_one()

            assert gw.status == "logined"
            assert len(received) == 1
            assert received[0].type == EventType.MD_LOGIN
            assert received[0].data["error_id"] == 0
            assert received[0].data["trading_day"] == "20260426"

    def test_on_rsp_user_login_failure(self):
        """OnRspUserLogin 失败不应改变状态为 logined"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine, broker_id="9999", user_id="test", password="123")
            gw.connect()

            spi = md_api.RegisterSpi.call_args[0][0]
            spi.OnFrontConnected()

            info = MagicMock()
            info.ErrorID = 3
            info.ErrorMsg = "密码错误"

            spi.OnRspUserLogin(MagicMock(), info, 1, True)

            assert gw.status != "logined"
            assert gw.status == "connected"

    def test_on_rtn_depth_market_data_puts_tick_event(self):
        """OnRtnDepthMarketData 应推送 EventType.TICK"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine)
            spi = self._connect_and_connected(gw, md_api)
            engine.process_one()  # consume EventType.MD_CONNECTED
            received = []
            engine.register(EventType.TICK, lambda e: received.append(e))

            tick = MagicMock()
            tick.InstrumentID = "rb2501"
            tick.LastPrice = 3500.0
            tick.Volume = 1000
            tick.OpenInterest = 50000
            tick.BidPrice1 = 3499.5
            tick.AskPrice1 = 3500.5
            tick.UpdateTime = "14:30:00"
            tick.UpdateMillisec = 500
            tick.HighestPrice = 3520.0
            tick.LowestPrice = 3480.0
            tick.OpenPrice = 3490.0
            tick.PreClosePrice = 3485.0
            tick.UpperLimitPrice = 3600.0
            tick.LowerLimitPrice = 3400.0
            tick.TradingDay = "20260426"
            tick.ActionDay = "20260426"

            spi.OnRtnDepthMarketData(tick)
            engine.process_one()

            assert len(received) == 1
            assert received[0].type == EventType.TICK
            assert received[0].data["instrument_id"] == "rb2501"
            assert received[0].data["last_price"] == 3500.0
            assert received[0].data["volume"] == 1000
            assert received[0].data["bid_price1"] == 3499.5
            assert received[0].data["ask_price1"] == 3500.5

    # _connect_and_connected is defined above — single copy

    def test_on_front_disconnected_puts_event(self):
        """OnFrontDisconnected 应推送 EventType.MD_DISCONNECTED"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine)
            spi = self._connect_and_connected(gw, md_api)
            engine.process_one()  # consume EventType.MD_CONNECTED
            received = []
            engine.register(EventType.MD_DISCONNECTED, lambda e: received.append(e))

            spi.OnFrontDisconnected(100)
            engine.process_one()

            assert gw.status == "disconnected"
            assert len(received) == 1
            assert received[0].data["reason"] == 100


class TestMdGatewaySubscribe:
    """测试订阅行情"""

    def _connect_and_connected(self, gw, md_api):
        """Helper: connect and simulate OnFrontConnected so gateway reaches CONNECTED"""
        gw.connect()
        spi = md_api.RegisterSpi.call_args[0][0]
        spi.OnFrontConnected()
        return spi

    def test_subscribe_calls_subscribe_market_data(self):
        """subscribe() 应调用 SubscribeMarketData"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine)
            self._connect_and_connected(gw, md_api)

            gw.subscribe(["rb2501", "rb2510"])
            md_api.SubscribeMarketData.assert_called_once_with([b"rb2501", b"rb2510"], 2)

    def test_subscribe_not_connected_raises(self):
        """未连接时 subscribe 应抛异常"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine)

            with pytest.raises(RuntimeError, match="not connected"):
                gw.subscribe(["rb2501"])

    def test_subscribe_single_instrument(self):
        """订阅单个合约"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine)
            self._connect_and_connected(gw, md_api)

            gw.subscribe("rb2501")
            md_api.SubscribeMarketData.assert_called_once_with([b"rb2501"], 1)



class TestMdGatewayLogin:
    """测试登录自动行为"""

    def test_auto_login_on_front_connected(self):
        """连接成功后应自动调用 ReqUserLogin"""
        engine = EventEngine()
        md_api = make_mock_md_api()

        with patch("trader.gateway.md_gateway.mdapi") as mock_mdapi:
            mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
            from trader.gateway.md_gateway import MdGateway
            gw = MdGateway(engine, broker_id="9999", user_id="test", password="123")
            gw.connect()

            spi = md_api.RegisterSpi.call_args[0][0]

            # 触发 OnFrontConnected → 应自动登录
            spi.OnFrontConnected()

            md_api.ReqUserLogin.assert_called_once()
            # 验证登录参数
            req = md_api.ReqUserLogin.call_args[0][0]
            assert req.BrokerID == "9999"
            assert req.UserID == "test"
            assert req.Password == "123"
