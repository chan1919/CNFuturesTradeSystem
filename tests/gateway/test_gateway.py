from unittest.mock import MagicMock

import pytest

from src.common.contract import Contract
from src.common.exchange import Exchange
from src.event_bus.event import Event, EventType
from src.event_bus.event_bus import EventBus


pytestmark = pytest.mark.gateway


def make_contract(symbol="rb2501"):
    return Contract(
        instrument_id=symbol,
        exchange=Exchange.SHFE,
        multiplier=10,
        tick_size=1.0,
    )


def make_gateway(event_bus=None):
    from src.gateway.gateway import Gateway

    return Gateway(event_bus or EventBus())


class TestGatewayContracts:
    def test_add_contract_stores_and_returns_by_instrument_id(self):
        gw = make_gateway()
        contract = make_contract()

        gw.add_contract(contract)

        assert gw.get_contract("rb2501") is contract

    def test_contracts_property_returns_copy(self):
        gw = make_gateway()
        contract = make_contract()
        gw.add_contract(contract)

        contracts = gw.contracts
        contracts.clear()

        assert gw.get_contract("rb2501") is contract


class TestGatewayAccountEvents:
    def test_trade_event_updates_account_position_for_known_contract(self):
        event_bus = EventBus()
        gw = make_gateway(event_bus)
        gw.add_contract(make_contract())

        event_bus.put(Event(EventType.TRADE, data={
            "instrument_id": "rb2501",
            "direction": "buy",
            "offset_flag": "open",
            "volume": 3,
            "price": 3500.0,
        }))
        event_bus.process_one()

        pos = gw.account.get_position("rb2501")
        assert pos is not None
        assert pos.long_today == 3
        assert pos.long_avg_price == 3500.0

    def test_trade_event_ignores_unknown_contract(self):
        event_bus = EventBus()
        gw = make_gateway(event_bus)

        event_bus.put(Event(EventType.TRADE, data={
            "instrument_id": "unknown",
            "direction": "buy",
            "offset_flag": "open",
            "volume": 1,
            "price": 3500.0,
        }))
        event_bus.process_one()

        assert gw.account.positions == {}

    def test_position_event_updates_account_for_known_contract(self):
        event_bus = EventBus()
        gw = make_gateway(event_bus)
        gw.add_contract(make_contract())

        event_bus.put(Event(EventType.POSITION, data={
            "instrument_id": "rb2501",
            "direction": "long",
            "yd_position": 5,
            "today_position": 2,
            "frozen": 1,
        }))
        event_bus.process_one()

        pos = gw.account.get_position("rb2501")
        assert pos is not None
        assert pos.long_yd == 5
        assert pos.long_today == 2
        assert pos.long_frozen == 1

    def test_tick_event_updates_existing_position_last_price(self):
        event_bus = EventBus()
        gw = make_gateway(event_bus)
        contract = make_contract()
        gw.add_contract(contract)
        gw.account.get_or_create(contract)

        event_bus.put(Event(EventType.TICK, data={
            "instrument_id": "rb2501",
            "last_price": 3510.0,
        }))
        event_bus.process_one()

        assert gw.account.get_position("rb2501").last_price == 3510.0

    def test_account_event_updates_funds(self):
        event_bus = EventBus()
        gw = make_gateway(event_bus)

        event_bus.put(Event(EventType.ACCOUNT, data={
            "balance": 150000.0,
            "available": 80000.0,
            "curr_margin": 50000.0,
            "frozen_margin": 10000.0,
            "frozen_cash": 5000.0,
            "position_profit": 12000.0,
            "commission": 3000.0,
            "pre_balance": 140000.0,
        }))
        event_bus.process_one()

        assert gw.account.balance == 150000.0
        assert gw.account.available == 80000.0
        assert gw.account.curr_margin == 50000.0
        assert gw.account.frozen_margin == 10000.0
        assert gw.account.frozen_cash == 5000.0
        assert gw.account.position_profit == 12000.0
        assert gw.account.commission == 3000.0
        assert gw.account.pre_balance == 140000.0


class TestGatewayDelegation:
    def test_delegates_market_and_trade_operations(self):
        gw = make_gateway()
        gw._md = MagicMock()
        gw._td = MagicMock()
        gw._td.send_order.return_value = "123"

        gw.connect()
        gw.subscribe("rb2501")
        order_ref = gw.send_order("rb2501", "buy", "open", 3500.0, 1)
        gw.cancel_order("rb2501", "123", 1, 100, "sys001")
        gw.query_positions()
        gw.query_account_info()
        gw.query_instruments()
        gw.qry_settlement_info("20260428")
        gw.settlement_info_confirm()
        gw.close()

        gw._md.connect.assert_called_once()
        gw._td.connect.assert_called_once()
        gw._md.subscribe.assert_called_once_with("rb2501")
        gw._td.send_order.assert_called_once_with("rb2501", "buy", "open", 3500.0, 1)
        assert order_ref == "123"
        gw._td.cancel_order.assert_called_once_with("rb2501", "123", 1, 100, "sys001")
        gw._td.query_positions.assert_called_once()
        gw._td.query_account.assert_called_once()
        gw._td.query_instruments.assert_called_once()
        gw._td.qry_settlement_info.assert_called_once_with("20260428")
        gw._td.settlement_info_confirm.assert_called_once()
        gw._md.close.assert_called_once()
        gw._td.close.assert_called_once()
