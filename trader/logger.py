import logging
import sys
from datetime import datetime
from pathlib import Path

from trader.event import EventType

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

LOG_EVENTS = [
    EventType.TD_CONNECTED,
    EventType.TD_DISCONNECTED,
    EventType.TD_LOGIN,
    EventType.TD_AUTHENTICATE,
    EventType.MD_CONNECTED,
    EventType.MD_DISCONNECTED,
    EventType.MD_LOGIN,
    EventType.ORDER,
    EventType.TRADE,
    EventType.POSITION,
    EventType.ACCOUNT,
    EventType.TICK,
    EventType.SYSTEM,
    EventType.SETTLEMENT_INFO,
    EventType.SETTLEMENT_INFO_CONFIRMED,
]


class LogHandler:
    def __init__(self, event_engine, level=logging.INFO):
        self._ee = event_engine
        self._logger = logging.getLogger("CNFutures")
        self._logger.setLevel(level)
        self._logger.handlers.clear()

        now = datetime.now()
        month_dir = LOG_DIR / now.strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)
        date_str = now.strftime("%Y-%m-%d")

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        trade_path = month_dir / f"trade_{date_str}.log"
        fh = logging.FileHandler(trade_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        self._logger.addHandler(fh)

        error_path = month_dir / f"error_{date_str}.log"
        eh = logging.FileHandler(error_path, encoding="utf-8")
        eh.setLevel(logging.ERROR)
        eh.setFormatter(formatter)
        self._logger.addHandler(eh)

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

        for et in LOG_EVENTS:
            self._ee.register(et.value, self._on_event)

    def close(self):
        for et in LOG_EVENTS:
            self._ee.unregister(et.value, self._on_event)
        self._logger.handlers.clear()

    def _on_event(self, event):
        msg = self._format(event)
        level = (event.data or {}).get("log_level", "info").lower()
        if level == "error":
            self._logger.error(msg)
        elif level == "warning":
            self._logger.warning(msg)
        elif level == "debug":
            self._logger.debug(msg)
        else:
            self._logger.info(msg)

    @staticmethod
    def _format(event):
        type_name = event.type.value
        data = event.data or {}
        parts = [f"[{type_name}]"]
        keys = [
            "instrument_id", "error_id", "error_msg", "order_ref",
            "trade_id", "order_status", "last_price", "volume",
            "balance", "available", "curr_margin", "position_profit",
            "trading_day", "front_id", "session_id", "reason",
            "app_id", "user_id", "price", "direction", "offset_flag",
        ]
        for key in keys:
            val = data.get(key)
            if val is not None:
                parts.append(f"{key}={val}")
        return " ".join(parts)
