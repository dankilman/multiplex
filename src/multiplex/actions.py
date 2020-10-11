from dataclasses import dataclass
from typing import List


class Action:
    pass


class BoxAction:
    def run(self, box_holder):
        raise NotImplementedError


@dataclass
class SetTitle(BoxAction):
    title: str

    def run(self, box_holder):
        box_holder.iterator.title = self.title


class Collapse(BoxAction):
    def run(self, box_holder):
        box_holder.box.toggle_collapse(True)


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
            action.run(box_holder)
