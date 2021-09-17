from dataclasses import dataclass
from typing import Union


@dataclass
class Process:
    cmd: Union[str, list, tuple]

    @property
    def title(self):
        return self.cmd if isinstance(self.cmd, str) else " ".join(self.cmd)
