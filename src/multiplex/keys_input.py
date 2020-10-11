import asyncio
import os
import sys
import select
import termios
import tty

from multiplex import keys as _keys

initial_stdin_settings = None


def setup():
    global initial_stdin_settings
    initial_stdin_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())


def restore():
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, initial_stdin_settings)


def _has_data():
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])


class InputReader:
    def __init__(self, viewer, bindings):
        self.viewer = viewer
        self.bindings = bindings
        self.pending = []

    async def read(self):
        while True:
            result = self._read_iteration()
            if result is not None:
                yield -1, result
            await asyncio.sleep(0.02)

    def _read_iteration(self):
        if not _has_data():
            return None
        skip_process = False
        while _has_data():
            key = os.read(sys.stdin.fileno(), 1)
            key_ord = ord(key)
            if key_ord in _keys.BACKSPACE_OR_DEL:
                self.pending = self.pending[:-1]
                skip_process = True
                break
            else:
                self.pending.append(key_ord)
        if not skip_process:
            result, pending = self._process(self.pending)
            self.pending = pending
        else:
            result = []
        return result

    def _process(self, keys):
        viewer = self.viewer
        bindings = self.bindings
        if viewer.help.show:
            mode = _keys.HELP
        elif not viewer.focused.state.auto_scroll:
            mode = _keys.SCROLL
        else:
            mode = _keys.NORMAL
        sequences = [bindings[mode], bindings[_keys.GLOBAL]]

        result = []
        while keys:
            has_pending = False
            found_sequence = False
            for mode_sequences in sequences:
                for key_sequence, fn in mode_sequences.items():
                    common_prefix = os.path.commonprefix([tuple(keys), key_sequence])
                    if common_prefix:
                        if len(common_prefix) == len(key_sequence):
                            result.append(fn)
                            keys = keys[len(key_sequence) :]
                            found_sequence = True
                            break
                        elif list(key_sequence)[: len(keys)] == keys:
                            has_pending = True
            if has_pending:
                break
            if not found_sequence:
                keys = keys[1:]
        return result, keys
