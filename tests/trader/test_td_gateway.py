"""TDD: TdGateway 测试"""
import pytest
from unittest.mock import MagicMock, patch
from trader.engine import EventEngine
from trader.event import Event, EventType


def make_mock_td_api():
    api = MagicMock()
    api.GetTradingDay.return_value = "20260426"
    return api


class TestTdGatewayConnect:
    def test_connect_calls_register_front_and_init(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine, front_url="tcp://127.0.0.1:10100")
            gw.connect()

            td_api.RegisterFront.assert_called_once_with("tcp://127.0.0.1:10100")
            td_api.RegisterSpi.assert_called_once()
            td_api.SubscribePrivateTopic.assert_called_once()
            td_api.SubscribePublicTopic.assert_called_once()
            td_api.Init.assert_called_once()

    def test_connect_changes_status(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine, front_url="tcp://127.0.0.1:10100")
            gw.connect()
            assert gw.status == "connecting"


class TestTdGatewayCallbacks:
    def _connect_and_connected(self, gw, td_api):
        gw.connect()
        spi = td_api.RegisterSpi.call_args[0][0]
        spi.OnFrontConnected()
        return spi

    def test_on_front_connected_puts_event(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine, front_url="tcp://127.0.0.1:10100")
            gw.connect()

            spi = td_api.RegisterSpi.call_args[0][0]
            received = []
            engine.register(EventType.TD_CONNECTED, lambda e: received.append(e))

            spi.OnFrontConnected()
            engine.process_one()

            assert gw.status == "connected"
            assert len(received) == 1
            assert received[0].type == EventType.TD_CONNECTED

    def test_on_rsp_user_login_puts_event(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine, broker_id="9999", user_id="test", password="123")
            gw.connect()

            spi = td_api.RegisterSpi.call_args[0][0]
            spi.OnFrontConnected()
            engine.process_one()

            received = []
            engine.register(EventType.TD_LOGIN, lambda e: received.append(e))

            rsp = MagicMock()
            rsp.FrontID = 1
            rsp.SessionID = 100
            rsp.MaxOrderRef = "1"
            rsp.LoginTime = "09:00:00"
            rsp.TradingDay = "20260426"

            info = MagicMock()
            info.ErrorID = 0
            info.ErrorMsg = ""

            spi.OnRspUserLogin(rsp, info, 1, True)
            engine.process_one()

            assert gw.status == "logined"
            assert gw.front_id == 1
            assert gw.session_id == 100
            assert len(received) == 1
            assert received[0].data["error_id"] == 0

    def test_on_rtn_order_puts_event(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine)
            spi = self._connect_and_connected(gw, td_api)
            engine.process_one()

            received = []
            engine.register(EventType.ORDER, lambda e: received.append(e))

            order = MagicMock()
            order.InstrumentID = "rb2501"
            order.OrderRef = "123"
            order.Direction = "0"
            order.OrderStatus = "3"
            order.VolumeTotalOriginal = 10
            order.VolumeTraded = 0
            order.LimitPrice = 3500.0
            order.InsertTime = "14:30:00"

            spi.OnRtnOrder(order)
            engine.process_one()

            assert len(received) == 1
            assert received[0].data["instrument_id"] == "rb2501"
            assert received[0].data["order_ref"] == "123"

    def test_on_rtn_trade_puts_event(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine)
            spi = self._connect_and_connected(gw, td_api)
            engine.process_one()

            received = []
            engine.register(EventType.TRADE, lambda e: received.append(e))

            trade = MagicMock()
            trade.InstrumentID = "rb2501"
            trade.TradeID = "trade001"
            trade.OrderRef = "123"
            trade.Direction = "0"
            trade.OffsetFlag = "0"
            trade.Price = 3500.0
            trade.Volume = 5
            trade.TradeDate = "20260426"
            trade.TradeTime = "14:30:05"

            spi.OnRtnTrade(trade)
            engine.process_one()

            assert len(received) == 1
            assert received[0].data["trade_id"] == "trade001"
            assert received[0].data["price"] == 3500.0
            assert received[0].data["volume"] == 5

    def test_on_rsp_qry_investor_position(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine)
            spi = self._connect_and_connected(gw, td_api)
            engine.process_one()

            received = []
            engine.register(EventType.POSITION, lambda e: received.append(e))

            pos = MagicMock()
            pos.InstrumentID = "rb2501"
            pos.PosiDirection = "2"
            pos.PositionDate = "1"
            pos.YdPosition = 10
            pos.TodayPosition = 5
            pos.PositionProfit = 500.0
            pos.UseMargin = 10000.0

            spi.OnRspQryInvestorPosition(pos, MagicMock(ErrorID=0), 1, True)
            engine.process_one()

            assert len(received) >= 1
            assert received[0].data["instrument_id"] == "rb2501"

    def test_on_rsp_qry_trading_account(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine)
            spi = self._connect_and_connected(gw, td_api)
            engine.process_one()

            received = []
            engine.register(EventType.ACCOUNT, lambda e: received.append(e))

            acc = MagicMock()
            acc.AccountID = "668888"
            acc.PreBalance = 100000.0
            acc.Balance = 150000.0
            acc.Available = 80000.0
            acc.CurrMargin = 50000.0
            acc.FrozenMargin = 10000.0
            acc.PositionProfit = 5000.0

            spi.OnRspQryTradingAccount(acc, MagicMock(ErrorID=0), 1, True)
            engine.process_one()

            assert len(received) == 1
            assert received[0].data["balance"] == 150000.0
            assert received[0].data["available"] == 80000.0


class TestTdGatewaySendOrder:
    def _connect_and_logined(self, gw, td_api):
        gw.connect()
        spi = td_api.RegisterSpi.call_args[0][0]
        spi.OnFrontConnected()
        # simulate auto login success
        rsp = MagicMock()
        rsp.FrontID = 1
        rsp.SessionID = 100
        rsp.MaxOrderRef = "1"
        spi.OnRspUserLogin(rsp, MagicMock(ErrorID=0), 1, True)
        return spi

    def test_send_order_calls_req_order_insert(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine, broker_id="9999", user_id="test", password="123")
            self._connect_and_logined(gw, td_api)
            engine.process_one()  # consume EventType.TD_LOGIN
            engine.process_one()  # consume EventType.TD_CONNECTED

            order_ref = gw.send_order(
                instrument_id="rb2501",
                direction="buy",
                offset_flag="open",
                price=3500.0,
                volume=10,
            )

            td_api.ReqOrderInsert.assert_called_once()
            req = td_api.ReqOrderInsert.call_args[0][0]
            assert req.InstrumentID == "rb2501"
            assert req.LimitPrice == 3500.0
            assert req.VolumeTotalOriginal == 10
            assert order_ref is not None

    def test_send_order_not_logined_raises(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine)

            with pytest.raises(RuntimeError, match="not logined"):
                gw.send_order("rb2501", "buy", "open", 3500.0, 10)

    def test_send_order_increments_order_ref(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine, broker_id="9999", user_id="test", password="123")
            self._connect_and_logined(gw, td_api)

            ref1 = gw.send_order("rb2501", "buy", "open", 3500.0, 10)
            ref2 = gw.send_order("rb2510", "sell", "close", 3510.0, 5)

            assert ref1 != ref2


class TestTdGatewayCancelOrder:
    def _connect_and_logined(self, gw, td_api):
        gw.connect()
        spi = td_api.RegisterSpi.call_args[0][0]
        spi.OnFrontConnected()
        rsp = MagicMock()
        rsp.FrontID = 1
        rsp.SessionID = 100
        rsp.MaxOrderRef = "1"
        spi.OnRspUserLogin(rsp, MagicMock(ErrorID=0), 1, True)
        return spi

    def test_cancel_order_calls_req_order_action(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine, broker_id="9999", user_id="test", password="123")
            self._connect_and_logined(gw, td_api)

            gw.cancel_order(instrument_id="rb2501", order_ref="123", front_id=1, session_id=100, order_sys_id="sys001")

            td_api.ReqOrderAction.assert_called_once()
            req = td_api.ReqOrderAction.call_args[0][0]
            assert req.OrderRef == "123"
            assert req.FrontID == 1
            assert req.SessionID == 100
            assert req.OrderSysID == "sys001"

    def test_cancel_order_not_logined_raises(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine)

            with pytest.raises(RuntimeError, match="not logined"):
                gw.cancel_order("rb2501", "123", 1, 100, "sys001")


class TestTdGatewayQuery:
    def _connect_and_logined(self, gw, td_api):
        gw.connect()
        spi = td_api.RegisterSpi.call_args[0][0]
        spi.OnFrontConnected()
        rsp = MagicMock()
        rsp.FrontID = 1
        rsp.SessionID = 100
        rsp.MaxOrderRef = "1"
        spi.OnRspUserLogin(rsp, MagicMock(ErrorID=0), 1, True)
        return spi

    def test_query_positions_calls_req_qry(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine, broker_id="9999", user_id="test", password="123")
            self._connect_and_logined(gw, td_api)

            gw.query_positions()
            td_api.ReqQryInvestorPosition.assert_called_once()

    def test_query_account_calls_req_qry(self):
        engine = EventEngine()
        td_api = make_mock_td_api()

        with patch("trader.gateway.td_gateway.tdapi") as mock_tdapi:
            mock_tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi.return_value = td_api
            from trader.gateway.td_gateway import TdGateway
            gw = TdGateway(engine, broker_id="9999", user_id="test", password="123")
            self._connect_and_logined(gw, td_api)

            gw.query_account()
            td_api.ReqQryTradingAccount.assert_called_once()