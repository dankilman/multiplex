import asyncio

from multiplex.actions import SetTitle, Collapse


class Controller:
    def __init__(self, title, thread_safe=False, loop=None):
        self.title = title
        self.queue = asyncio.Queue()
        self.thread_safe = thread_safe
        self.loop = loop or asyncio.get_event_loop()

    def write(self, data):
        if self.thread_safe:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, data)
        else:
            self.queue.put_nowait(data)

    def set_title(self, title):
        self.write(SetTitle(title))

    def collapse(self):
        self.write(Collapse())
