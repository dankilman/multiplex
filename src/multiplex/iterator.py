import asyncio
import types
import pathlib

import aiofiles
import colorful as cf
from aiostream.stream import create, combine
from multiplex.actions import SetTitle, Collapse, BoxActions, UpdateMetadata


async def stream_reader_generator(reader):
    while True:
        b = await reader.read(1000000)
        if not b:
            break
        yield b.decode()


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
    name_attr = getattr(obj, "__name__", None)
    if name_attr:
        return name_attr
    class_attr = getattr(obj, "__class__", None)
    if class_attr:
        name_attr = getattr(class_attr, "__name__", None)
        if name_attr:
            return name_attr
    return None


def _to_iterator(obj, title):
    if isinstance(obj, str):
        title = _extract_title(title, obj)
        obj = asyncio.subprocess.create_subprocess_shell(
            obj,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
            assert streams
            if len(streams) == 1:
                stream = streams[0]
            else:
                stream = combine.merge(*streams)
            async for data in stream:
                yield data
            exit_code = await proc.wait()
            status = cf.red("✗") if exit_code else cf.green("✓")
            yield BoxActions(
                [
                    UpdateMetadata({"exit_code": exit_code}),
                    SetTitle(f"[{status}] {title}"),
                    Collapse(),
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
    else:
        inner_type = "N/A"
    if title is None:
        title = "N/A"
    return obj, title, inner_type


def to_iterator(obj, title=None):
    result = obj if isinstance(obj, Iterator) else Iterator(obj, title)
    if title is not None and result.title is None:
        result.title = title
    return result
