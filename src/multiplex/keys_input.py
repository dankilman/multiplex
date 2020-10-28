import asyncio
import functools
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
        is_input = self.viewer.is_input_mode
        keys = []
        while _has_data():
            key = os.read(sys.stdin.fileno(), 1)
            key_ord = ord(key)
            if is_input:
                keys.append(key)
            if not is_input and key_ord in _keys.BACKSPACE_OR_DEL:
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
        if is_input and keys:
            result.append(functools.partial(self._read_input_handler, keys))
        return result

    @staticmethod
    async def _read_input_handler(keys, viewer):
        if not viewer.is_input_mode:
            return
        writer = viewer.focused.holder.iterator.metadata.get("input")
        if not writer:
            return
        writer.write(b"".join(keys))
        await writer.drain()

    def _process(self, keys):
        viewer = self.viewer
        bindings = self.bindings
        if viewer.help.show:
            mode = _keys.HELP
        elif viewer.is_input_mode:
            mode = _keys.INPUT
        elif viewer.is_scrolling:
            mode = _keys.SCROLL
        else:
            mode = _keys.NORMAL
        sequences = [bindings[mode]]
        if mode != _keys.INPUT:
            sequences.append(bindings[_keys.GLOBAL])

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
