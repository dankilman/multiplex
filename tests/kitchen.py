import argparse
import asyncio
import io
import random
import threading
import time

import colors
from colors.colors import _color_code as cc


from multiplex import ansi
from multiplex import Multiplex, Controller
from multiplex.logging import init_logging


def run(multi, *other):
    future = asyncio.gather(multi.run_async(), *other)
    try:
        asyncio.get_event_loop().run_until_complete(future)
    except KeyboardInterrupt:
        pass
    finally:
        multi.cleanup()


def run_simple():
    async def text_generator(index):
        for i in range(num_iterations):
            output = f"iterator-number-#{index + 1}-({i + 1})|" * 7
            output = f"{output}\n"
            yield output
            await asyncio.sleep(random.random() / 10)
            await asyncio.sleep(0.5)
        yield "done"

    num_iterations = 2000
    num_iterators = 20
    iterators = [(text_generator(i), f"It #{i + 1}") for i in range(num_iterators)]
    return iterators


def run_colors():
    async def text_generator():
        for i in range(num_iterations):
            r = random.randint(0, 256)
            g = random.randint(0, 256)
            b = random.randint(0, 256)
            output = "".join(f'{colors.color(f"hello-{i}-", (r, g, b))}' for i in range(30))
            output = f"{output}\n"
            yield output
            await asyncio.sleep(random.random() / 10)
        yield "done"

    num_iterations = 2000
    num_iterators = 3
    iterators = [(text_generator, f"It #{i + 1}") for i in range(num_iterators)]
    return iterators


def run_dynamic():
    async def text_generator():
        for i in range(num_iterations):
            for j in range(10000):
                yield "hello"
                await asyncio.sleep(0.1)
                yield "\rgoodbye"
                await asyncio.sleep(0.1)
                yield "\r" + ansi.CLEAR_LINE
            yield "\n"
            await asyncio.sleep(random.random() / 10)
            await asyncio.sleep(0.5)
        yield "done"

    num_iterations = 2000
    num_iterators = 3
    iterators = [(text_generator, f"It #{i + 1}") for i in range(num_iterators)]
    return iterators


def run_style():
    async def text_generator():
        for i in range(num_iterations):

            fr = random.randint(0, 256)
            fg = random.randint(0, 256)
            fb = random.randint(0, 256)

            br = random.randint(0, 256)
            bg = random.randint(0, 256)
            bb = random.randint(0, 256)

            def code(*codes):
                return f'{ansi.CSI}{";".join(str(c) for c in codes)}m'

            reset = code(0)

            text_buffer = io.StringIO()
            for j in range(100):
                text_buffer.write(code(cc("red", 30)))
                text_buffer.write(code(cc("green", 40)))
                text_buffer.write(f"some text {j} ")
                text_buffer.write(code(cc((fr, fg, fb), 30)))
                text_buffer.write(code(cc((br, bg, bb), 40)))
                text_buffer.write(f"some text {j} ")
                text_buffer.write(code(3, 4, 7))
                text_buffer.write(f"some text {j} ")
                text_buffer.write(code(24, 9, 1))
                text_buffer.write(f"some text {j} ")
                text_buffer.write(reset)
            output = text_buffer.getvalue()
            output = f"{output}\n"
            yield output
            await asyncio.sleep(random.random() / 10)
            await asyncio.sleep(0.5)
        yield "done"

    num_iterations = 2000
    num_iterators = 3
    iterators = [(text_generator, f"It #{i + 1}") for i in range(num_iterators)]
    return iterators


def run_processes():
    return ["gls -la --group-directories-first --color=always"]


def run_controller():
    multplex = Multiplex()
    c1 = Controller("runner1")
    c2 = Controller("runner2")
    multplex.add(c1)
    multplex.add(c2)

    async def runner(c):
        c.write("some data 1\n")
        await asyncio.sleep(1)
        c.write("some data 2\n")
        await asyncio.sleep(1)
        c.write("some data 2\n")
        await asyncio.sleep(1)
        c.write("some data 2\n")
        c.set_title(f"{c.title} [done]")
        c.collapse()

    run(multplex, runner(c1), runner(c2))


def run_controller_thread_safe():
    multiplex = Multiplex()
    c1 = Controller("runner1", thread_safe=True)
    c2 = Controller("runner2", thread_safe=True)
    multiplex.add(c1)
    multiplex.add(c2)

    def runner(c):
        c.write("some data 1\n")
        time.sleep(1)
        c.write("some data 2\n")
        time.sleep(1)
        c.write("some data 2\n")
        time.sleep(1)
        c.write("some data 2\n")
        c.set_title(f"{c.title} [done]")
        c.collapse()

    threads = [threading.Thread(target=runner, args=(c,)) for c in [c1, c2]]
    for t in threads:
        t.daemon = True
        t.start()
    run(multiplex)


def run_live():
    obj = "echo $RANDOM; sleep 5; echo $RANDOM"

    multi = Multiplex(box_height=3)

    async def runner():
        while not multi.viewer or not multi.viewer.stopped:
            multi.add(obj)
            await asyncio.sleep(0.1)

    run(multi, runner())


def run_live_thread_safe():
    obj = "echo $RANDOM; sleep 5; echo $RANDOM"

    multi = Multiplex(box_height=3)

    loop = asyncio.get_event_loop()

    def runner(_):
        asyncio.set_event_loop(loop)
        while not multi.viewer or not multi.viewer.stopped:
            multi.add(obj, thread_safe=True)
            time.sleep(1)

    threads = [threading.Thread(target=runner, args=(c,)) for c in [1]]
    for t in threads:
        t.daemon = True
        t.start()
    run(multi)


whats = {
    "1": run_simple,
    "2": run_processes,
    "3": run_colors,
    "4": run_dynamic,
    "5": run_style,
    "6": run_controller,
    "7": run_controller_thread_safe,
    "8": run_live,
    "9": run_live_thread_safe,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("what")
    return parser.parse_args()


def main():
    init_logging()
    args = parse_args()
    fn = whats.get(args.what, run_simple)
    result = fn()
    if isinstance(result, list):
        multi = Multiplex(verbose=True)
        for i in result:
            title = None
            if isinstance(i, tuple):
                i, title = i
            multi.add(i, title)
        multi.run()


if __name__ == "__main__":
    main()
