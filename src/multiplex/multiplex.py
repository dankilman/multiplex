import asyncio
import os
from typing import List

from multiplex.viewer import Viewer
from multiplex.iterator import Descriptor
from multiplex.ipc import Server


class Multiplex:
    def __init__(self, verbose=False, box_height=None, output_path=None, socket_path=None, buffer_lines=None):
        self.descriptors: List[Descriptor] = []
        self.verbose = verbose
        self.box_height = box_height
        self.buffer_lines = buffer_lines
        self.output_path = output_path or os.getcwd()
        self.server = Server(socket_path)
        self.viewer: Viewer = None

    def run(self, load=None):
        try:
            asyncio.run(self.run_async(load))
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    async def run_async(self, load=None):
        assert not self.viewer
        self.viewer = Viewer(
            descriptors=self.descriptors,
            verbose=self.verbose,
            box_height=self.box_height,
            socket_path=self.server.socket_path,
            output_path=self.output_path,
            buffer_lines=self.buffer_lines,
        )
        if load:
            await self.viewer.load(load)
        await self.server.start(viewer=self.viewer)
        try:
            await self.viewer.run()
        finally:
            self.server.stop()

    def add(self, obj, title=None, box_height=None, thread_safe=False):
        descriptor = Descriptor(obj=obj, title=title, box_height=box_height, scroll_down=self.viewer is not None)
        self.descriptors.append(descriptor)
        if self.viewer:
            self.viewer.add(descriptor, thread_safe=thread_safe)

    def add_thread_safe(self, obj, title=None, box_height=None):
        self.add(obj, title, box_height, thread_safe=True)

    def cleanup(self):
        if self.viewer:
            if not self.viewer.stopped:
                self.viewer.restore()
            for it in self.viewer.iterators:
                close = it.metadata.get("close")
                if close:
                    close()
        if self.server and not self.server.stopped:
            self.server.stop()

    @property
    def socket_path(self):
        return self.server.socket_path
