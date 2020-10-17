from dataclasses import dataclass
from typing import List

from multiplex.ansi import C
from multiplex.refs import SPLIT


class Action:
    pass


class BoxAction:
    def run(self, box_holder):
        raise NotImplementedError


@dataclass
class SetTitle(BoxAction):
    title: str

    def run(self, box_holder):
        title = self.title
        iterator = box_holder.iterator
        if iterator.iterator is SPLIT:
            title += f" ({iterator.title})"
        iterator.title = title


class ToggleCollapse(BoxAction):
    value = None

    def run(self, box_holder):
        box_holder.box.toggle_collapse(self.value)


class Collapse(ToggleCollapse):
    value = True


class Expand(ToggleCollapse):
    value = False


@dataclass
class UpdateMetadata(BoxAction):
    metadata: dict

    def run(self, box_holder):
        box_holder.iterator.metadata.update(self.metadata)


@dataclass
class BoxActions(BoxAction):
    actions: List[BoxAction]

    def run(self, box_holder):
        for action in self.actions:
            if isinstance(action, BoxAction):
                action.run(box_holder)
            elif callable(action):
                action(box_holder)
            else:
                raise RuntimeError(f"Invalid action: {action}")
