from typing import List

from multiplex import Viewer
from multiplex.iterator import Iterator, to_iterator
from multiplex.controller import Controller


class ViewBuilder:
    def __init__(self, verbose=False):
        self.iterators: List[Iterator] = []
        self.verbose = verbose

    def build(self):
        return Viewer(self.iterators, verbose=self.verbose)

    def add(self, obj):
        self.iterators.append(to_iterator(obj))

    def new_controller(self, title=None, thread_safe=False, loop=None) -> Controller:
        result = Controller(
            title=title,
            thread_safe=thread_safe,
            loop=loop,
        )
        self.add(result)
        return result
