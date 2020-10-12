import asyncio
import fcntl
import io
import os
import struct
import termios
import types
import pathlib
import pty

import aiofiles
from aiostream.stream import create, combine
from multiplex import ansi
from multiplex.actions import SetTitle, BoxActions, UpdateMetadata, Collapse
from multiplex.ansi import C, RED_RGB, GREEN_RGB
from multiplex.controller import Controller

STOP = object()


async def stream_reader_generator(reader):
    while True:
        try:
            b = await reader.read(1000000)
            if not b:
                break
            yield b.decode()
        except OSError:
            return


class Iterator:
    def __init__(self, iterator, title=None):
        iterator, title, inner_type = _to_iterator(iterator, title)
        self.iterator = iterator
        self.title = title
        self.inner_type = inner_type
        self.metadata = {}


def _extract_title(current_title, obj):
    if current_title is not None:
        return current_title
    if isinstance(obj, str):
        return obj
    title_attr = getattr(obj, "title", None)
    if title_attr:
        return title_attr
    name_attr = getattr(obj, "__name__", None)
    if name_attr:
        return name_attr
    class_attr = getattr(obj, "__class__", None)
    if class_attr:
        name_attr = getattr(class_attr, "__name__", None)
        if name_attr:
            return name_attr
    return None


def _setsize(fd, rows=0, cols=0):
    if not (rows and cols):
        cols, rows = ansi.get_size()
    s = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, s)


def _to_iterator(obj, title):
    master, slave = None, None

    if isinstance(obj, str):
        title = _extract_title(title, obj)
        master, slave = pty.openpty()
        _setsize(slave)
        obj = asyncio.subprocess.create_subprocess_shell(
            obj,
            stdin=slave,
            stdout=slave,
            stderr=slave,
        )

    if isinstance(obj, types.FunctionType):
        title = _extract_title(title, obj)
        obj = obj()
    elif isinstance(obj, types.MethodType):
        title = _extract_title(title, obj)
        obj = obj()

    if isinstance(obj, types.CoroutineType):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("Iterators cannot be created from coroutines when the event loop is already running")
        obj = loop.run_until_complete(obj)

    if isinstance(obj, asyncio.streams.StreamReader):
        title = _extract_title(title, obj)
        obj = stream_reader_generator(obj)
        inner_type = "stream_reader"
    elif isinstance(obj, types.AsyncGeneratorType):
        title = _extract_title(title, obj)
        inner_type = "async_generator"
    elif isinstance(obj, types.GeneratorType):
        title = _extract_title(title, obj)
        obj = create.from_iterable.raw(obj)
        inner_type = "generator"
    elif hasattr(obj, "__aiter__"):
        title = _extract_title(title, obj)
        inner_type = "async_iterable"
    elif hasattr(obj, "__iter__"):
        title = _extract_title(title, obj)
        obj = create.from_iterable.raw(obj)
        inner_type = "iterable"
    elif isinstance(obj, asyncio.subprocess.Process):

        async def g():
            stdout = proc.stdout
            stderr = proc.stderr
            streams = []
            if isinstance(stdout, asyncio.streams.StreamReader):
                streams.append(stream_reader_generator(stdout))
            if isinstance(stderr, asyncio.streams.StreamReader):
                streams.append(stream_reader_generator(stderr))
            if master:
                assert slave
                reader_pipe = io.open(master, "rb", 0)
                reader = asyncio.StreamReader()
                reader_protocol = asyncio.StreamReaderProtocol(reader)
                await asyncio.get_running_loop().connect_read_pipe(lambda: reader_protocol, reader_pipe)
                streams.append(stream_reader_generator(reader))

                async def exit_stream():
                    await proc.wait()
                    if slave:
                        os.close(slave)
                    yield

                streams.append(exit_stream())

            assert streams

            if len(streams) == 1:
                stream = streams[0]
            else:
                stream = combine.merge(*streams)
            async for data in stream:
                yield data
            exit_code = proc.returncode if slave else await proc.wait()
            status = C("✗", fg=RED_RGB) if exit_code else C("✓", fg=GREEN_RGB)
            yield BoxActions(
                [
                    UpdateMetadata({"exit_code": exit_code}),
                    SetTitle(C("[", status, f"] {title}")),
                    # Collapse(),
                ]
            )

        inner_type = "async_process"
        title = _extract_title(title, obj)
        proc = obj
        obj = g()
    elif isinstance(obj, pathlib.Path):

        async def g():
            async with aiofiles.open(file_path, encoding="utf-8") as f:
                async for line in f:
                    yield line

        title = str(obj)
        inner_type = "path"
        file_path = obj
        obj = g()
    elif isinstance(obj, Controller):

        async def g():
            while True:
                result = await controller.queue.get()
                if result is STOP:
                    break
                yield result

        title = _extract_title(title, obj)
        inner_type = "controller"
        controller = obj
        obj = g()
    else:
        inner_type = "N/A"
    if title is None:
        title = "N/A"
    return obj, title, inner_type


def to_iterator(obj, title=None) -> Iterator:
    result = obj if isinstance(obj, Iterator) else Iterator(obj, title)
    if title is not None and result.title is None:
        result.title = title
    return result
