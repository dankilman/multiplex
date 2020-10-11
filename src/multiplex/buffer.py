import io
import shutil

import pyte
from pyte import graphics as g
from pyte.screens import Char, wcwidth

from multiplex.ansi import CSI

TERMINATE = "m"

UNDEFINED = object()
RESET_TEXT_ATTRS = set(list(range(1, 10)))
BOLD = 1

empty_meta = Char(
    None,
    fg=None,
    bg=None,
    bold=(),
    italics=None,
    underscore=None,
    strikethrough=None,
    reverse=None,
)

reset = f"{CSI}0{TERMINATE}"
index_to_char_meta = {0: empty_meta}
char_meta_to_index = {empty_meta: 0}
index_to_ansi = {0: reset}

counter = 0


class Screen(pyte.Screen):
    def reset(self):
        original_columns = self.columns
        original_lines = self.lines
        self.columns = 1
        self.lines = 1
        super().reset()
        self.cursor.attrs = self.default_char
        self.dirty.clear()
        self.columns = original_columns
        self.lines = original_lines

    @property
    def default_char(self):
        return Char(data=" ", fg=0)

    def select_graphic_rendition(self, *attrs):
        if not attrs or attrs == (0,):
            self.cursor.attrs = self.default_char
            return

        fg = UNDEFINED
        bg = UNDEFINED
        added_text_attrs = set()
        removed_text_attrs = set()

        attrs = list(reversed(attrs))
        while attrs:
            attr = attrs.pop()
            if attr == 0:
                fg = None
                bg = None
                removed_text_attrs = RESET_TEXT_ATTRS
            elif attr in g.FG_ANSI:
                fg = (attr,)
            elif attr in g.BG:
                bg = (attr,)
            elif attr in g.FG_AIXTERM:
                fg = (attr,)
                added_text_attrs.add(BOLD)
            elif attr in g.BG_AIXTERM:
                bg = (attr,)
                added_text_attrs.add(BOLD)
            elif attr in (g.FG_256, g.BG_256):
                n = attrs.pop()
                if n == 5:
                    value = attr, n, attrs.pop()
                    if attr == g.FG_256:
                        fg = value
                    else:
                        bg = value
                elif n == 2:
                    value = attr, n, attrs.pop(), attrs.pop(), attrs.pop()
                    if attr == g.FG_256:
                        fg = value
                    else:
                        bg = value
            elif 1 <= attr <= 9:
                added_text_attrs.add(attr)
            elif 21 <= attr <= 29:
                removed_text_attrs.add(attr)

        current_meta = index_to_char_meta[self.cursor.attrs.fg]
        current_text_attrs = set(current_meta.bold)
        new_text_attrs = (current_text_attrs | added_text_attrs) - removed_text_attrs

        replace = {}
        if fg is not UNDEFINED:
            replace["fg"] = fg
        if bg is not UNDEFINED:
            replace["bg"] = bg
        replace["bold"] = tuple(sorted(new_text_attrs))
        new_char_meta = current_meta._replace(**replace)

        if new_char_meta in char_meta_to_index:
            index = char_meta_to_index[new_char_meta]
        else:
            global counter
            counter += 1
            index = counter
            char_meta_to_index[new_char_meta] = index
            index_to_char_meta[index] = new_char_meta
            codes = []
            c = new_char_meta
            if c.fg:
                codes.extend(c.fg)
            if c.bg:
                codes.extend(c.bg)
            if c.bold:
                codes.extend(list(c.bold))
            ansi = f'{CSI}{";".join(str(c) for c in codes)}{TERMINATE}'
            index_to_ansi[index] = ansi

        self.cursor.attrs = Char(" ", fg=index)

    @property
    def display(self):
        # overriding this so we don't evaluate all virtual lines/columns
        # when debugging, etc...
        return []


class LinedBuffer:
    BIG = 1000000

    def __init__(self, width=None):
        self.width = width or self.BIG
        self.screen = Screen(lines=self.BIG, columns=self.width)
        self.stream = pyte.Stream(screen=self.screen)
        self.max_line = -1
        self.raw_to_self = {}
        self.self_to_raw = {}

    def write(self, data):
        self.stream.feed(data)
        return self._update()

    @property
    def num_lines(self):
        return self.max_line + 1

    def _update(self):
        dirty = self.screen.dirty
        if dirty:
            dirty_list = sorted(list(dirty))
            self.max_line = max(self.max_line, *dirty_list)
            self.screen.dirty.clear()
            return dirty_list
        return []

    def get_lines(self, lines, start_line, columns, start_column):
        result = []
        num_lines = self.num_lines
        if start_line > num_lines - 1:
            return result
        last_char_meta_index = 0
        buffer = self.screen.buffer
        for line_num in range(start_line, lines + start_line):
            screen_line = buffer[line_num]
            keys = screen_line.keys()
            line_length = max(keys) if keys else 0
            is_wide_char = False
            current_line_buffer = io.StringIO()
            for x in range(start_column, columns + start_column):
                if is_wide_char:  # Skip stub
                    is_wide_char = False
                    continue
                current_char = screen_line[x]
                char_meta_index = current_char.fg
                if char_meta_index != last_char_meta_index:
                    current_line_buffer.write(reset)
                    if char_meta_index:
                        current_line_buffer.write(index_to_ansi[char_meta_index])
                    last_char_meta_index = char_meta_index
                char_data = current_char.data
                current_line_buffer.write(char_data)
                assert sum(map(wcwidth, char_data[1:])) == 0
                is_wide_char = wcwidth(char_data[0]) == 2
            # add reset at the end
            if last_char_meta_index and line_num == lines + start_line - 1:
                current_line_buffer.write(reset)
            result.append((line_length, current_line_buffer.getvalue()))
        return result


class Buffer:
    def __init__(self, width=None):
        self.raw_buffer = io.StringIO()
        self.raw_lines = 0
        self.lined_buffer = LinedBuffer()
        self.wrapping_buffer = self._new_wrapping_buffer(width)

    @staticmethod
    def _new_wrapping_buffer(width):
        return LinedBuffer(width or shutil.get_terminal_size().columns)

    def get_lines(self, lines, start_line, columns, start_column, wrap=False):
        return self._get_buffer(wrap).get_lines(
            lines=lines,
            start_line=start_line,
            columns=columns,
            start_column=start_column,
        )

    def write(self, data, buffers=None, skip_raw=False):
        if not skip_raw:
            self.raw_buffer.write(data)
        buffers = buffers or (self.lined_buffer, self.wrapping_buffer)
        lines = data.split("\n")
        for i, line in enumerate(lines):
            if not skip_raw and i:
                self.raw_lines += 1
            if i < len(lines) - 1:
                line = f"{line}\r\n"
            current_raw_line = self.raw_lines if not skip_raw else i
            for buffer in buffers:
                dirty_lines = buffer.write(line)
                if dirty_lines:
                    buffer.raw_to_self[current_raw_line] = dirty_lines[0]
                    for dl in dirty_lines:
                        buffer.self_to_raw[dl] = current_raw_line

    @property
    def width(self):
        return self.wrapping_buffer.width

    @width.setter
    def width(self, value):
        self.wrapping_buffer = self._new_wrapping_buffer(value)
        old_location = self.raw_buffer.tell()
        self.raw_buffer.seek(0)
        self.write(self.raw_buffer.read(), skip_raw=True, buffers=[self.wrapping_buffer])
        self.raw_buffer.seek(old_location)

    def get_num_lines(self, wrap=False):
        return self._get_buffer(wrap).num_lines

    @property
    def num_lines(self):
        return self.get_num_lines(False)

    @property
    def wrapped_num_lines(self):
        return self.get_num_lines(True)

    def _get_buffer(self, wrap):
        return self.wrapping_buffer if wrap else self.lined_buffer

    def convert_line_number(self, line_number, from_wrapped=False):
        from_buffer = self.wrapping_buffer if from_wrapped else self.lined_buffer
        to_buffer = self.lined_buffer if from_wrapped else self.wrapping_buffer
        raw_line_number = from_buffer.self_to_raw.get(line_number)
        if raw_line_number is None:
            # TODO log warning
            return 0
        to_line_number = to_buffer.raw_to_self.get(raw_line_number)
        if to_line_number is None:
            # TODO log warning
            return 0
        return to_line_number
