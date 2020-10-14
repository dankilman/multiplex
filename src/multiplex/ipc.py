import asyncio
import json
import os
import tempfile
from asyncio import StreamWriter, StreamReader
from random import randint

from multiplex import Viewer


class Server:
    def __init__(self):
        self.socket_path = f"{tempfile.gettempdir()}/multiplex-{randint(100000, 999999)}"
        self.viewer: Viewer = None
        self.server = None
        self.server_task = None
        self.stopped = False

    async def start(self, viewer):
        self.viewer = viewer
        self.server = await asyncio.start_unix_server(
            client_connected_cb=self._handle_request,
            path=self.socket_path,
        )
        self.server_task = asyncio.create_task(self.server.serve_forever())

    def stop(self):
        if self.server_task:
            self.server_task.cancel()
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
        self.stopped = True

    async def _handle_request(self, reader: StreamReader, writer: StreamWriter):
        request = await _read_message(reader)
        response = await self._handle_message(request)
        await _write_message(response, writer)
        writer.close()

    async def _handle_message(self, message):
        action = message.get("action")
        if action == "split":
            self.viewer.restore()
        return {"hello": "there"}


class Client:
    def __init__(self, socket_path):
        self._socket_path = socket_path

    async def split(self):
        response = await self._request({"action": "split"})
        print(response)

    async def _connect(self):
        return await asyncio.open_unix_connection(self._socket_path)

    async def _request(self, message):
        reader, writer = await self._connect()
        await _write_message(message, writer)
        response = await _read_message(reader)
        writer.close()
        return response


async def _read_message(reader):
    return json.loads((await reader.readline()).decode().strip())


async def _write_message(message, writer):
    writer.write(f"{json.dumps(message)}\n".encode())
    await writer.drain()
