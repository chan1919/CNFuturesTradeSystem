"""TDD Step 1: 先写 Event 和 EventBus 的测试"""

# import pytest
# import time
# import threading
from src.event_bus.event import Event, EventType
from src.event_bus.event_bus import EventBus


class TestEvent:
    """测试 Event 数据类"""

    def test_create_event(self):
        """创建一个事件，验证类型和数据"""
        event = Event(
            type=EventType.TICK, data={"instrument_id": "rb2501", "last_price": 3500.0}
        )
        assert event.type == EventType.TICK
        assert event.data["instrument_id"] == "rb2501"
        assert event.data["last_price"] == 3500.0

    def test_event_default_data_is_none(self):
        """不传 data 时 data 应为 None"""
        event = Event(type=EventType.ORDER)
        assert event.type == EventType.ORDER
        assert event.data is None


class TestEventBus:
    """测试事件总线核心功能"""

    def test_register_handler(self):
        """注册处理器后引擎应正确记录"""
        event_bus = EventBus()

        def handler(event):
            pass

        event_bus.register(EventType.TICK, handler)
        assert handler in event_bus._handlers[EventType.TICK]

    def test_unregister_handler(self):
        """取消注册后处理器应被移除"""
        event_bus = EventBus()

        def handler(event):
            pass

        event_bus.register(EventType.TICK, handler)
        event_bus.unregister(EventType.TICK, handler)
        assert handler not in event_bus._handlers.get(EventType.TICK, [])

    def test_put_and_process(self):
        """放入事件后，已注册的处理器应被调用"""
        event_bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        event_bus.register(EventType.TICK, handler)
        event = Event(type=EventType.TICK, data={"price": 100})
        event_bus.put(event)

        # 手动处理一次
        event_bus.process_one()

        assert len(received) == 1
        assert received[0].data["price"] == 100

    def test_multiple_handlers_same_event(self):
        """同一事件类型可注册多个处理器"""
        event_bus = EventBus()
        results = []

        def handler1(event):
            results.append("h1")

        def handler2(event):
            results.append("h2")

        event_bus.register(EventType.TICK, handler1)
        event_bus.register(EventType.TICK, handler2)
        event_bus.put(Event(type=EventType.TICK))
        event_bus.process_one()

        assert results == ["h1", "h2"]

    def test_handler_not_called_for_different_event(self):
        """不应调用不匹配事件类型的处理器"""
        event_bus = EventBus()
        results = []

        def handler(event):
            results.append("called")

        event_bus.register(EventType.ORDER, handler)
        event_bus.put(Event(type=EventType.TICK))
        event_bus.process_one()

        assert len(results) == 0

    def test_run_stop(self):
        """start 后引擎应在后台线程运行，stop 后应停止"""
        event_bus = EventBus()
        results = []

        def handler(event):
            results.append(event)
            event_bus.stop()

        event_bus.register(EventType.TICK, handler)
        event_bus.start()
        event_bus.put(Event(type=EventType.TICK))
        event_bus.join(timeout=2)

        assert len(results) == 1

    def test_put_command_from_external(self):
        """外部指令也应通过 put() 进入单队列"""
        event_bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        event_bus.register("cmd.order", handler)
        event_bus.put(Event(type="cmd.order", data={"order_ref": "123"}))

        event_bus.process_one()

        assert len(received) == 1
        assert received[0].data["order_ref"] == "123"

    def test_start_sets_active_flag(self):
        """start 后 active 应为 True"""
        event_bus = EventBus()
        assert not event_bus.active
        event_bus.start()
        assert event_bus.active
        event_bus.stop()

    def test_stop_clears_active_flag(self):
        """stop 后 active 应为 False"""
        event_bus = EventBus()
        event_bus.start()
        event_bus.stop()
        assert not event_bus.active
