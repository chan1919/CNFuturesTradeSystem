from datetime import datetime

from main import RuntimeGuard
from trader.gateway.base import GatewayStatus


class DummyGateway:
    def __init__(self, status=GatewayStatus.DISCONNECTED):
        self.status = status
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1


class TestRuntimeGuard:
    def test_ensure_connected_connects_gateways_in_connection_window(self):
        md = DummyGateway()
        td = DummyGateway()
        guard = RuntimeGuard(md_gateway=md, td_gateway=td)

        triggered = guard.ensure_connected(now=datetime(2026, 4, 28, 9, 0, 0))

        assert triggered is True
        assert md.connect_calls == 1
        assert td.connect_calls == 1

    def test_ensure_connected_does_nothing_outside_connection_window(self):
        md = DummyGateway()
        td = DummyGateway()
        guard = RuntimeGuard(md_gateway=md, td_gateway=td)

        triggered = guard.ensure_connected(now=datetime(2026, 5, 2, 10, 0, 0))

        assert triggered is False
        assert md.connect_calls == 0
        assert td.connect_calls == 0

    def test_ensure_connected_skips_connected_gateways(self):
        md = DummyGateway(status=GatewayStatus.LOGINED)
        td = DummyGateway(status=GatewayStatus.DISCONNECTED)
        guard = RuntimeGuard(md_gateway=md, td_gateway=td)

        triggered = guard.ensure_connected(now=datetime(2026, 4, 28, 9, 0, 0))

        assert triggered is True
        assert md.connect_calls == 0
        assert td.connect_calls == 1

    def test_stop_prevents_auto_connect(self):
        md = DummyGateway()
        td = DummyGateway()
        guard = RuntimeGuard(md_gateway=md, td_gateway=td)
        guard.stop()

        triggered = guard.ensure_connected(now=datetime(2026, 4, 28, 9, 0, 0))

        assert triggered is False
        assert md.connect_calls == 0
        assert td.connect_calls == 0
