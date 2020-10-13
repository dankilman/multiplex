from typing import List

from multiplex import Viewer
from multiplex.iterator import Iterator, to_iterator, to_iterator_async


class Multiplex:
    def __init__(self, verbose=False, box_height=None):
        self.iterators: List[Iterator] = []
        self.verbose = verbose
        self.box_height = box_height
        self.viewer: Viewer = None

    def run(self):
        self._prepare()
        self.viewer.run()

    async def run_async(self):
        self._prepare()
        await self.viewer.run_async()

    def _prepare(self):
        assert not self.viewer
        self.viewer = Viewer(self.iterators, verbose=self.verbose, box_height=self.box_height)

    def add(self, obj, box_height=None, thread_safe=False):
        self._add(to_iterator(obj), box_height=box_height, thread_safe=thread_safe)

    async def add_async(self, obj, box_height=None, thread_safe=False):
        self._add(await to_iterator_async(obj), box_height=box_height, thread_safe=thread_safe)

    def _add(self, iterator, box_height, thread_safe):
        iterator.box_height = box_height
        self.iterators.append(iterator)
        if self.viewer:
            self.viewer.add(iterator, thread_safe=thread_safe)
