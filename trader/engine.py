from collections import defaultdict
import queue
import threading

from trader.event import Event


class EventEngine:
    def __init__(self):
        self._queue = queue.Queue()
        self._handlers = defaultdict(list)
        self._active = False
        self._thread = None

    @property
    def active(self) -> bool:
        return self._active

    def register(self, event_type: str, handler):
        self._handlers[event_type].append(handler)

    def unregister(self, event_type: str, handler):
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def put(self, event: Event):
        self._queue.put(event)

    def process_one(self):
        try:
            event = self._queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self._dispatch(event)

    def start(self):
        self._active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._active = False

    def join(self, timeout=None):
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self):
        while self._active:
            self.process_one()

    def _dispatch(self, event: Event):
        for handler in self._handlers.get(event.type, []):
            handler(event)