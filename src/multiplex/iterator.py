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


def _str_to_iterator(str_value, title):
    def _setsize(fd):
        cols, rows = ansi.get_size()
        s = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, s)

    title = _extract_title(title, str_value)
    master, slave = pty.openpty()
    _setsize(slave)
    obj = asyncio.subprocess.create_subprocess_shell(
        str_value,
        stdin=slave,
        stdout=slave,
        stderr=slave,
    )
    return obj, title, (master, slave)


def _coroutine_to_iterator(cor):
    loop = asyncio.get_event_loop()
    if loop.is_running():
        raise RuntimeError("Iterators cannot be created from coroutines when the event loop is already running")
    return loop.run_until_complete(cor)


def _process_to_iterator(process, title, master, slave):
    async def exit_stream():
        await process.wait()
        if slave:
            os.close(slave)
        yield

    async def g():
        stdout = process.stdout
        stderr = process.stderr
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
            streams.extend([stream_reader_generator(reader), exit_stream()])

        assert streams

        if len(streams) == 1:
            stream = streams[0]
        else:
            stream = combine.merge(*streams)
        async for data in stream:
            yield data
        exit_code = process.returncode if slave else await process.wait()
        status = C("✗", fg=RED_RGB) if exit_code else C("✓", fg=GREEN_RGB)
        yield BoxActions(
            [
                UpdateMetadata({"exit_code": exit_code}),
                SetTitle(C("[", status, f"] {title}")),
                # Collapse(),
            ]
        )

    obj = g()
    title = _extract_title(title, process)
    inner_type = "async_process"
    return obj, title, inner_type


def _path_to_iterator(file_path):
    async def g():
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            async for line in f:
                yield line

    obj = g()
    title = str(file_path)
    inner_type = "path"
    return obj, title, inner_type


def _controller_to_iterator(controller, title):
    async def g():
        while True:
            result = await controller.queue.get()
            if result is STOP:
                break
            yield result

    obj = g()
    title = _extract_title(title, controller)
    inner_type = "controller"
    return obj, title, inner_type


def _stream_reader_to_iterator(stream_reader, title):
    obj = stream_reader_generator(stream_reader)
    title = _extract_title(title, stream_reader)
    inner_type = "stream_reader"
    return obj, title, inner_type


def _async_generator_to_iterator(agen, title):
    obj = agen
    title = _extract_title(title, agen)
    inner_type = "async_generator"
    return obj, title, inner_type


def _generator_to_iterator(gen, title):
    obj = create.from_iterable.raw(gen)
    title = _extract_title(title, gen)
    inner_type = "generator"
    return obj, title, inner_type


def _async_iterable_to_iterator(aiter, title):
    obj = aiter
    title = _extract_title(title, aiter)
    inner_type = "async_iterable"
    return obj, title, inner_type


def _iterable_to_iterator(_iter, title):
    obj = create.from_iterable.raw(_iter)
    title = _extract_title(title, _iter)
    inner_type = "iterable"
    return obj, title, inner_type


def _callable_to_iterator(cb, title):
    obj = cb()
    title = _extract_title(title, cb)
    return obj, title


def _to_iterator(obj, title):
    master, slave = None, None
    if isinstance(obj, str):
        obj, title, (master, slave) = _str_to_iterator(obj, title)

    if isinstance(obj, (types.FunctionType, types.MethodType)):
        obj, title = _callable_to_iterator(obj, title)

    if isinstance(obj, types.CoroutineType):
        obj = _coroutine_to_iterator(obj)

    inner_type = "N/A"
    if isinstance(obj, asyncio.streams.StreamReader):
        obj, title, inner_type = _stream_reader_to_iterator(obj, title)
    elif isinstance(obj, types.AsyncGeneratorType):
        obj, title, inner_type = _async_generator_to_iterator(obj, title)
    elif isinstance(obj, types.GeneratorType):
        obj, title, inner_type = _generator_to_iterator(obj, title)
    elif hasattr(obj, "__aiter__"):
        obj, title, inner_type = _async_iterable_to_iterator(obj, title)
    elif hasattr(obj, "__iter__"):
        obj, title, inner_type = _iterable_to_iterator(obj, title)
    elif isinstance(obj, asyncio.subprocess.Process):
        obj, title, inner_type = _process_to_iterator(obj, title, master, slave)
    elif isinstance(obj, pathlib.Path):
        obj, title, inner_type = _path_to_iterator(obj)
    elif isinstance(obj, Controller):
        obj, title, inner_type = _controller_to_iterator(obj, title)

    if title is None:
        title = "N/A"

    return obj, title, inner_type


def to_iterator(obj, title=None) -> Iterator:
    return obj if isinstance(obj, Iterator) else Iterator(obj, title)
