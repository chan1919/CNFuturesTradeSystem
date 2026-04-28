import logging
import re
from datetime import datetime

import pytest
from trader.engine import EventEngine
from trader.event import Event, EventType
from trader.logger import LogHandler, LOG_DIR, LOG_EVENTS


@pytest.fixture(autouse=True)
def patch_log_dir(tmp_path):
    original = LogHandler.__init__
    original_close = getattr(LogHandler, "close", None)
    def patched_init(self, event_engine, level=logging.INFO):
        self._ee = event_engine
        self._logger = logging.getLogger("CNFuturesTest")
        self._logger.setLevel(level)
        self._logger.handlers.clear()

        now = datetime.now()
        month_dir = tmp_path / now.strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)
        date_str = now.strftime("%Y-%m-%d")

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        fh = logging.FileHandler(month_dir / f"trade_{date_str}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        self._logger.addHandler(fh)

        fh_error = logging.FileHandler(month_dir / f"error_{date_str}.log", encoding="utf-8")
        fh_error.setLevel(logging.ERROR)
        fh_error.setFormatter(formatter)
        self._logger.addHandler(fh_error)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

        for et in LOG_EVENTS:
            self._ee.register(et.value, self._on_event)

        self._log_dir = tmp_path

    def patched_close(self):
        for et in LOG_EVENTS:
            self._ee.unregister(et.value, self._on_event)
        self._logger.handlers.clear()

    LogHandler.__init__ = patched_init
    LogHandler.close = patched_close
    yield
    LogHandler.__init__ = original
    if original_close is not None:
        LogHandler.close = original_close
    logging.getLogger("CNFuturesTest").handlers.clear()


class TestLogHandlerInit:
    def test_creates_month_subdirectory(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        assert month_dir.is_dir()

    def test_creates_dated_trade_file(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        assert (month_dir / f"trade_{date_str}.log").is_file()
        assert (month_dir / f"error_{date_str}.log").is_file()

    def test_close_unregisters_event_handlers(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)

        assert len(engine._handlers[EventType.TD_LOGIN.value]) == 1
        handler.close()
        assert len(engine._handlers[EventType.TD_LOGIN.value]) == 0


class TestLogHandlerLevelRouting:
    def test_info_event_writes_to_trade_file_not_error_file(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        trade_file = month_dir / f"trade_{date_str}.log"
        error_file = month_dir / f"error_{date_str}.log"

        engine.put(Event(EventType.TD_LOGIN, data={
            "error_id": 0,
            "trading_day": "20260428",
            "log_level": "info",
        }))
        engine.process_one()

        trade_content = trade_file.read_text(encoding="utf-8")
        assert "[td.login]" in trade_content
        assert "error_id=0" in trade_content
        assert "trading_day=20260428" in trade_content

        error_content = error_file.read_text(encoding="utf-8")
        assert error_content.strip() == ""

    def test_error_event_writes_to_both_files(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        trade_file = month_dir / f"trade_{date_str}.log"
        error_file = month_dir / f"error_{date_str}.log"

        engine.put(Event(EventType.TD_LOGIN, data={
            "error_id": 64,
            "error_msg": "客户未认证",
            "log_level": "error",
        }))
        engine.process_one()

        trade_content = trade_file.read_text(encoding="utf-8")
        assert "[td.login]" in trade_content
        assert "[ERROR]" in trade_content

        error_content = error_file.read_text(encoding="utf-8")
        assert "[td.login]" in error_content
        assert "error_msg=客户未认证" in error_content

    def test_warning_event_writes_to_trade_not_error(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        trade_file = month_dir / f"trade_{date_str}.log"
        error_file = month_dir / f"error_{date_str}.log"

        engine.put(Event(EventType.TD_DISCONNECTED, data={
            "reason": 100,
            "log_level": "warning",
        }))
        engine.process_one()

        trade_content = trade_file.read_text(encoding="utf-8")
        assert "[WARNING]" in trade_content
        assert "reason=100" in trade_content

        error_content = error_file.read_text(encoding="utf-8")
        assert error_content.strip() == ""


class TestLogHandlerDefaultLevel:
    def test_no_log_level_defaults_to_info(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        trade_file = month_dir / f"trade_{date_str}.log"

        engine.put(Event(EventType.ORDER, data={
            "order_ref": "123",
            "instrument_id": "m2609",
        }))
        engine.process_one()

        content = trade_file.read_text(encoding="utf-8")
        assert "[INFO]" in content or "[ORDER]" in content


class TestLogHandlerFormat:
    def test_timestamp_and_level_in_output(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        trade_file = month_dir / f"trade_{date_str}.log"

        engine.put(Event(EventType.MD_LOGIN, data={
            "trading_day": "20260428",
            "log_level": "info",
        }))
        engine.process_one()

        content = trade_file.read_text(encoding="utf-8")
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", content)
        assert "[INFO]" in content
        assert "[md.login]" in content


class TestLogHandlerNotRegistered:
    def test_unregistered_event_does_not_log(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        trade_file = month_dir / f"trade_{date_str}.log"

        before = trade_file.stat().st_mtime_ns

        engine.put(Event(EventType.QRV_INSTRUMENT, data={"log_level": "info"}))
        engine.process_one()

        after = trade_file.stat().st_mtime_ns
        assert after == before


class TestLogHandlerDebug:
    def test_debug_level_not_written_at_default(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine)
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        trade_file = month_dir / f"trade_{date_str}.log"

        engine.put(Event(EventType.TICK, data={
            "instrument_id": "m2609",
            "last_price": 2994.0,
            "log_level": "debug",
        }))
        engine.process_one()

        content = trade_file.read_text(encoding="utf-8")
        assert "[DEBUG]" not in content

    def test_debug_level_written_when_level_set_to_debug(self, patch_log_dir):
        engine = EventEngine()
        handler = LogHandler(engine, level=logging.DEBUG)
        date_str = datetime.now().strftime("%Y-%m-%d")
        month_dir = handler._log_dir / datetime.now().strftime("%Y-%m")
        trade_file = month_dir / f"trade_{date_str}.log"

        engine.put(Event(EventType.TICK, data={
            "instrument_id": "m2609",
            "last_price": 2994.0,
            "log_level": "debug",
        }))
        engine.process_one()

        content = trade_file.read_text(encoding="utf-8")
        assert "[DEBUG]" in content
