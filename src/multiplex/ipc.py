import asyncio
import json
import os
import tempfile
from asyncio import StreamWriter, StreamReader
from random import randint

from multiplex.viewer import Viewer
from multiplex.iterator import Descriptor, MULTIPLEX_SOCKET_PATH


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
        self._handle_message(request)
        await _write_message({"status": "success"}, writer)
        writer.close()

    def _handle_message(self, message):
        action = message.pop("action")
        if action == "split":
            self.viewer.split(**message)
        elif action == "collapse":
            self.viewer.focused.toggle_collapse(**message)
            self.viewer.events.send_redraw()
        elif action == "add":
            self.viewer.add(Descriptor(**message))
        elif action == "save":
            self.viewer.events.send_save()
        elif action == "quit":
            self.viewer.events.send_quit()
        elif action == "batch":
            for action in message["actions"]:
                self._handle_message(action)


class Client:
    def __init__(self, socket_path):
        self._socket_path = socket_path

    async def add(self, obj, title, box_height):
        await self._request(self.add_request_body(obj, title, box_height))

    @staticmethod
    def add_request_body(obj, title, box_height):
        return {"action": "add", "obj": obj, "title": title, "box_height": box_height}

    async def split(self, title, box_height):
        await self._request(self.split_request_body(title, box_height))

    @staticmethod
    def split_request_body(title, box_height):
        return {"action": "split", "title": title, "box_height": box_height}

    async def toggle_collapse(self, value=None):
        await self._request(self.collapse_request_body(value))

    @staticmethod
    def collapse_request_body(value):
        return {"action": "collapse", "value": value}

    async def save(self):
        await self._request(self.save_request_body())

    @staticmethod
    def save_request_body():
        return {"action": "save"}

    async def quit(self):
        await self._request(self.quit_request_body())

    @staticmethod
    def quit_request_body():
        return {"action": "quit"}

    async def batch(self, actions):
        await self._request({"action": "batch", "actions": actions})

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


def get_env_socket_path():
    return os.environ.get(MULTIPLEX_SOCKET_PATH)
