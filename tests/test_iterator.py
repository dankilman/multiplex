import asyncio
import os

from aiostream import streamcontext
from aiostream.test_utils import assert_aiter
import pytest

from multiplex import iterator as _iterator
from multiplex.controller import Controller
from multiplex.iterator import to_iterator, STOP

pytestmark = pytest.mark.asyncio

ACTION = object()


async def collect(source):
    result = []
    async with streamcontext(source) as streamer:
        async for item in streamer:
            result.append(item)
    return result


@pytest.fixture
def patch_actions(monkeypatch):
    monkeypatch.setattr(_iterator, "BoxActions", lambda *_, **__: ACTION)


async def test_async_generator_input():
    async def g():
        for i in range(1):
            yield i

    iterator = await to_iterator(g())
    assert iterator.title == "g"
    assert iterator.inner_type == "async_generator"
    await assert_aiter(iterator.iterator, [0])


async def test_generator_input():
    def g():
        for i in range(1):
            yield i

    iterator = await to_iterator(g())
    assert iterator.title == "g"
    assert iterator.inner_type == "generator"
    await assert_aiter(iterator.iterator, [0])


async def test_async_process_pipe_stdout(patch_actions):
    p = await asyncio.subprocess.create_subprocess_shell(
        cmd="printf 1; sleep 0.01; printf 2",
        stdout=asyncio.subprocess.PIPE,
    )
    iterator = await to_iterator(p)
    assert iterator.title == "Process"
    assert iterator.inner_type == "async_process"
    await assert_aiter(iterator.iterator, ["1", "2", ACTION])


async def test_async_process_pipe_stderr(patch_actions):
    p = await asyncio.subprocess.create_subprocess_shell(
        cmd="printf 1 1>&2",
        stderr=asyncio.subprocess.PIPE,
    )
    iterator = await to_iterator(p)
    assert iterator.title == "Process"
    assert iterator.inner_type == "async_process"
    await assert_aiter(iterator.iterator, ["1", ACTION])


async def test_async_process_pipe_stdout_stederr(patch_actions):
    p = await asyncio.subprocess.create_subprocess_shell(
        cmd="""
            printf 1 1>&2 && \
            sleep 0.01 && \
            printf 2 && \
            sleep 0.01 && \
            printf 3 1>&2 && \
            sleep 0.01 && \
            printf 4 
        """,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    iterator = await to_iterator(p)
    assert iterator.title == "Process"
    assert iterator.inner_type == "async_process"
    await assert_aiter(iterator.iterator, ["1", "2", "3", "4", ACTION])


async def test_async_process_pipe_backslash_r(patch_actions):
    p = await asyncio.subprocess.create_subprocess_shell(
        cmd=f"printf hello; sleep 0.01; printf \r; echo goodbye",
        stdout=asyncio.subprocess.PIPE,
    )
    iterator = await to_iterator(p)
    assert iterator.title == "Process"
    assert iterator.inner_type == "async_process"
    await assert_aiter(
        iterator.iterator,
        [
            "hello",
            "\rgoodbye\n",
            ACTION,
        ],
    )


async def test_async_stream_reader():
    p = await asyncio.subprocess.create_subprocess_shell(
        cmd="printf 1; sleep 0.01; printf 2",
        stdout=asyncio.subprocess.PIPE,
    )
    iterator = await to_iterator(p.stdout)
    assert iterator.title == "StreamReader"
    assert iterator.inner_type == "stream_reader"
    await assert_aiter(iterator.iterator, ["1", "2"])


async def test_async_iter():
    class It:
        def __init__(self, values):
            self.current_index = 0
            self.values = values

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.current_index < len(self.values) - 1:
                index = self.current_index
                self.current_index += 1
                return self.values[index]
            raise StopAsyncIteration

    vals = [1, 2, 3]
    iterator = await to_iterator(It(vals))
    assert iterator.title == "It"
    assert iterator.inner_type == "async_iterable"
    await assert_aiter(iterator.iterator, vals)


async def test_iterable():
    class It:
        def __init__(self, values):
            self.current_index = 0
            self.values = values

        def __iter__(self):
            return self

        def __next__(self):
            if self.current_index < len(self.values) - 1:
                index = self.current_index
                self.current_index += 1
                return self.values[index]
            raise StopIteration

    vals = [1, 2, 3]
    iterator = await to_iterator(It(vals))
    assert iterator.title == "It"
    assert iterator.inner_type == "iterable"
    await assert_aiter(iterator.iterator, vals)


async def test_coroutine(patch_actions):
    c = asyncio.subprocess.create_subprocess_shell(
        cmd="printf hello",
        stdout=asyncio.subprocess.PIPE,
    )
    iterator = await to_iterator(c)
    assert iterator.title == "Process"
    assert iterator.inner_type == "async_process"
    await assert_aiter(iterator.iterator, ["hello", ACTION])


async def test_function():
    async def fn():
        yield "1"

    iterator = await to_iterator(fn)
    assert iterator.inner_type == "async_generator"
    assert iterator.title == "fn"
    await assert_aiter(iterator.iterator, ["1"])


async def test_method():
    class C:
        val1 = "1"
        val2 = "2"

        async def fn1(self):
            yield self.val1

        @classmethod
        async def fn2(cls):
            yield cls.val2

        @staticmethod
        async def fn3():
            yield "3"

    c = C()
    iterator = await to_iterator(c.fn1)
    assert iterator.title == "fn1"
    assert iterator.inner_type == "async_generator"
    await assert_aiter(iterator.iterator, ["1"])

    iterator = await to_iterator(c.fn2)
    assert iterator.title == "fn2"
    assert iterator.inner_type == "async_generator"
    await assert_aiter(iterator.iterator, ["2"])

    iterator = await to_iterator(c.fn3)
    assert iterator.title == "fn3"
    assert iterator.inner_type == "async_generator"
    await assert_aiter(iterator.iterator, ["3"])


async def test_path(tmp_path):
    path = tmp_path / "mock.txt"
    text = "hello\ngoodbye"
    path.write_text(text)
    iterator = await to_iterator(path)
    assert iterator.inner_type == "path"
    assert iterator.title == str(path)
    await assert_aiter(iterator.iterator, ["hello\n", "goodbye"])


async def test_str_async(patch_actions):
    cmd = "printf hello"
    iterator = await to_iterator(cmd)
    assert iterator.inner_type == "async_process"
    assert iterator.title == cmd
    await assert_aiter(iterator.iterator, ["hello", None, ACTION])


async def test_setsize(patch_actions, monkeypatch):
    cols = 100
    rows = 50
    monkeypatch.setenv("COLUMNS", str(cols))
    monkeypatch.setenv("LINES", str(rows))

    cmd = "stty size"
    iterator = await to_iterator(cmd)
    assert iterator.inner_type == "async_process"
    assert iterator.title == cmd
    items = await collect(iterator.iterator)
    assert items[0].strip() == f"{rows} {cols}"


async def test_controller():
    value = "data1"
    title = "title1"
    c = Controller(title)
    c.write(value)
    c.write(STOP)
    iterator = await to_iterator(c)
    assert iterator.inner_type == "controller"
    assert iterator.title == title
    await assert_aiter(iterator.iterator, [value])


async def test_controller_thead_safe():
    value = "data1"
    title = "title1"
    c = Controller(title, thread_safe=True)
    c.write(value)
    c.write(STOP)
    iterator = await to_iterator(c)
    assert iterator.inner_type == "controller"
    assert iterator.title == title
    await assert_aiter(iterator.iterator, [value])
