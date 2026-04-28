from datetime import datetime

from trader.common.trading_time import in_connection_window
from trader.gateway.base import GatewayStatus


class RuntimeGuard:
    def __init__(self, md_gateway=None, td_gateway=None, now_provider=None):
        self._md_gateway = md_gateway
        self._td_gateway = td_gateway
        self._now_provider = now_provider or datetime.now
        self._stopped = False
        self._connect_timeout_seconds = 30.0
        self._last_connect_attempt = {}

    def stop(self):
        self._stopped = True

    def ensure_connected(self, now=None):
        if self._stopped:
            return False

        current = now or self._now_provider()
        if not in_connection_window(current):
            return False

        triggered = False
        for gateway in (self._md_gateway, self._td_gateway):
            if gateway is None:
                continue
            if gateway.status == GatewayStatus.DISCONNECTED:
                gateway.connect()
                self._last_connect_attempt[gateway] = current
                triggered = True
                continue
            if gateway.status == GatewayStatus.CONNECTING:
                last_attempt = self._last_connect_attempt.get(gateway)
                if last_attempt is None:
                    self._last_connect_attempt[gateway] = current
                    continue
                elapsed = (current - last_attempt).total_seconds()
                if elapsed >= self._connect_timeout_seconds:
                    gateway.connect()
                    self._last_connect_attempt[gateway] = current
                    triggered = True
        return triggered


def main():
    # Runtime bootstrap will be expanded when real wiring is introduced.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
