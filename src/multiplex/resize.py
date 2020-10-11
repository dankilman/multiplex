import asyncio
import signal

RESIZE = object()


def setup(loop):
    queue = asyncio.Queue()

    def sigwinch():
        queue.put_nowait(True)

    loop.add_signal_handler(signal.SIGWINCH, sigwinch)

    async def gen():
        while True:
            await queue.get()
            yield RESIZE, None

    return gen()


def restore(loop):
    loop.remove_signal_handler(signal.SIGWINCH)
