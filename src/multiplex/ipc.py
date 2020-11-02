import asyncio
import json
import os
import tempfile
from asyncio import StreamWriter, StreamReader
from random import randint

from multiplex.exceptions import IPCException
from multiplex.viewer import Viewer
from multiplex.iterator import Descriptor, MULTIPLEX_STREAM_ID


class Server:
    def __init__(self, socket_path=None):
        self.socket_path = socket_path or f"{tempfile.gettempdir()}/multiplex-{randint(100000, 999999)}"
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
        try:
            await self._handle_message(request)
            response = {"status": "success"}
        except Exception as e:
            response = {"status": "failure", "error": str(e)}
        await _write_message(response, writer)
        writer.close()
        return response

    async def _handle_message(self, message, batch=False):
        action = message.pop("action")
        if action == "split":
            self.viewer.split(**message)
        elif action == "collapse":
            self.viewer.focused.toggle_collapse(**message)
            self.viewer.events.send_redraw()
        elif action == "add":
            descriptor = Descriptor(**message, scroll_down=True)
            handle = self.viewer.add(descriptor)
            if descriptor.wait:
                if batch:
                    return handle
                else:
                    await handle
        elif action == "save":
            self.viewer.events.send_save()
        elif action == "load":
            await self.viewer.load(**message)
        elif action == "quit":
            self.viewer.events.send_quit()
        elif action == "batch":
            handles = []
            for action in message["actions"]:
                handle = self._handle_message(action)
                if handle:
                    handles.append(handle)
            if handles:
                await asyncio.gather(*handles)


class Client:
    def __init__(self, socket_path):
        self._socket_path = socket_path

    async def add(self, obj, title, box_height, wait, cwd, env):
        await self._request(self.add_request_body(obj, title, box_height, wait, cwd, env))

    @staticmethod
    def add_request_body(obj, title, box_height, wait, cwd, env):
        return {
            "action": "add",
            "obj": obj,
            "title": title,
            "box_height": box_height,
            "wait": wait,
            "cwd": cwd,
            "env": env,
        }

    async def split(self, title, box_height, stream_id):
        await self._request(self.split_request_body(title, box_height, stream_id))

    @staticmethod
    def split_request_body(title, box_height, stream_id):
        return {"action": "split", "title": title, "box_height": box_height, "stream_id": stream_id}

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

    async def load(self, export_dir):
        await self._request(self.load_request_body(export_dir))

    @staticmethod
    def load_request_body(export_dir):
        return {"action": "load", "export_dir": export_dir}

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
        if response["status"] == "failure":
            raise IPCException(response["error"])
        return response


async def _read_message(reader):
    return json.loads((await reader.readline()).decode().strip())


async def _write_message(message, writer):
    writer.write(f"{json.dumps(message)}\n".encode())
    await writer.drain()


def get_env_stream_id():
    return os.environ.get(MULTIPLEX_STREAM_ID)
