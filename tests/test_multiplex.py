import asyncio
import os
import subprocess

import pytest
from multiplex import Multiplex, to_iterator, Controller
from multiplex.ipc import Client

pytestmark = pytest.mark.asyncio


def test_exports():
    assert Controller
    assert Multiplex
    assert to_iterator


@pytest.mark.skipif("os.environ.get('MULTIPLEX_SOCKET_PATH')", reason="Running in demo")
async def test_sanity(tmpdir):
    output_dir = tmpdir / "output"
    socket_echo = tmpdir / "socket_loc"
    output_dir.mkdir()
    cmd = f"mp 'echo 1' 'echo 2' 'echo $MULTIPLEX_SOCKET_PATH > {socket_echo}' -o {output_dir}"
    master, slave = os.openpty()
    proc = await asyncio.subprocess.create_subprocess_shell(
        cmd,
        stdin=slave,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    await asyncio.sleep(0.5)
    socket_path = socket_echo.read_text("utf-8").strip()
    client = Client(socket_path)
    await client.save()
    await client.quit()
    await proc.wait()
    output_dir = output_dir.listdir()[0]
    expected = ["1", "2", ""]
    listing = output_dir.listdir(sort=True)
    assert len(listing) == len(expected) + 1
    for i, ex in enumerate(expected):
        assert listing[i].read_text("utf-8").strip() == ex
