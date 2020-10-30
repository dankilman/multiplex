import asyncio

from multiplex.actions import SetTitle, ToggleCollapse, ToggleWrap
from multiplex.refs import STOP


class Controller:
    def __init__(self, title, thread_safe=False):
        self.title = title
        self.queue: asyncio.Queue = None
        self.thread_safe = thread_safe
        self._loop: asyncio.AbstractEventLoop = None
        self._pre_init_queue = []

    def _init(self):
        self.queue = asyncio.Queue()
        self._loop = asyncio.get_event_loop()
        for data in self._pre_init_queue:
            self.write(data)

    def write(self, data):
        if not self.queue:
            self._pre_init_queue.append(data)
            return
        if self.thread_safe:
            self._loop.call_soon_threadsafe(self.queue.put_nowait, data)
        else:
            self.queue.put_nowait(data)

    def set_title(self, title):
        self.write(SetTitle(title))

    def collapse(self):
        self.write(ToggleCollapse(True))

    def expand(self):
        self.write(ToggleCollapse(False))

    def toggle_collapse(self):
        self.write(ToggleCollapse())

    def wrap(self):
        self.write(ToggleWrap(True))

    def nowrap(self):
        self.write(ToggleWrap(False))

    def toggle_wrap(self):
        self.write(ToggleWrap())

    def done(self):
        self.write(STOP)
