import collections
import io
import shutil

import pyte
from pyte import graphics as g
from pyte.screens import Char, wcwidth, Margins

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
    def __init__(self, columns, lines, line_buffer):
        super().__init__(columns, lines)
        self.line_buffer = line_buffer

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
        self.tabstops = set(range(8, self.columns, 8))

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

    def erase_in_display(self, how=0, private=False):
        interval = None
        if how == 0:
            interval = range(self.cursor.y + 1, self.line_buffer.max_lines + 1)
        elif how == 1:
            interval = range(self.cursor.y)
        elif how == 2 or how == 3:
            interval = range(self.line_buffer.min_line, self.line_buffer.max_lines + 1)
        self.dirty.update(interval)
        for y in interval:
            line = self.buffer[y]
            for x in line:
                line[x] = self.cursor.attrs
        if how == 0 or how == 1:
            self.erase_in_line(how)

    def erase_in_line(self, how=0, private=False):
        self.dirty.add(self.cursor.y)
        line = self.buffer[self.cursor.y]
        keys = line.keys()
        columns = (max(keys) if keys else 0) + 1
        interval = None
        if how == 0:
            interval = range(self.cursor.x, columns)
        elif how == 1:
            interval = range(self.cursor.x + 1)
        elif how == 2:
            interval = range(columns)
        line = self.buffer[self.cursor.y]
        for x in interval:
            line[x] = self.cursor.attrs

    def index(self):
        self.cursor_down()

    def reverse_index(self):
        max_line = self.line_buffer.max_line
        min_line = self.line_buffer.min_line
        top, bottom = self.margins or Margins(min_line, max_line)
        if self.cursor.y == top:
            self.dirty.update(range(min_line, max_line + 1))
            for y in range(bottom, top, -1):
                self.buffer[y] = self.buffer[y - 1]
            self.buffer.pop(top, None)
        else:
            self.cursor_up()

    @property
    def display(self):
        # overriding this so we don't evaluate all virtual lines/columns
        # when debugging, etc...
        return []


class LinedBuffer:
    BIG = 1000000

    def __init__(self, width=None):
        self.width = width or self.BIG
        self.screen = Screen(lines=self.BIG, columns=self.width, line_buffer=self)
        self.stream = pyte.Stream(screen=self.screen)
        self.max_line = 0
        self.min_line = 0
        self.raw_to_self = {}
        self.self_to_raw = {}

    def write(self, data):
        self.stream.feed(data)
        return self._update()

    def _update(self):
        dirty = self.screen.dirty
        if dirty:
            dirty_list = sorted(list(dirty))
            self.max_line = max(self.max_line, *dirty_list)
            self.screen.dirty.clear()
            return dirty_list
        return []

    def remove_lines(self, lines, start_line):
        new_min_line = start_line + lines
        for i in range(start_line, new_min_line):
            self.screen.buffer.pop(i, None)
        return new_min_line

    def get_lines(self, lines, start_line, columns, start_column):
        result = []
        if start_line > self.max_line:
            return result
        last_char_meta_index = 0
        buffer = self.screen.buffer
        for line_num in range(start_line, lines + start_line):
            screen_line = buffer[line_num]
            keys = screen_line.keys()
            line_length = (max(keys) + 1) if keys else 0
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


class CappedRawBuffer:
    def __init__(self, buffer_lines):
        self._deque = collections.deque(maxlen=buffer_lines + 1)

    def write(self, data):
        if self._deque:
            data = self._deque.pop() + data
        self._deque.append(data)

    def writeline(self, line):
        self._deque.append(line)

    def newline(self):
        pass

    def getvalue(self):
        return "\n".join(self._deque)


class UncappedRawBuffer:
    def __init__(self):
        self._io = io.StringIO()

    def write(self, data):
        self._io.write(data)

    def writeline(self, line):
        self._io.write(line)

    def newline(self):
        self._io.write("\n")

    def getvalue(self):
        return self._io.getvalue()


class Buffer:
    def __init__(self, width=None, buffer_lines=None):
        self.buffer_lines = buffer_lines
        self.raw_buffer = CappedRawBuffer(buffer_lines) if buffer_lines else UncappedRawBuffer()
        self.raw_lines = 0
        self.lined_buffer = LinedBuffer()
        self.wrapping_buffer = self._new_wrapping_buffer(width)

    @staticmethod
    def _new_wrapping_buffer(width):
        return LinedBuffer(width or shutil.get_terminal_size().columns)

    def get_lines(self, lines, start_line, columns, start_column, wrap):
        return self._get_buffer(wrap).get_lines(
            lines=lines,
            start_line=start_line,
            columns=columns,
            start_column=start_column,
        )

    def write(self, data, buffers=None, skip_raw=False):
        buffers = buffers or (self.lined_buffer, self.wrapping_buffer)
        lines = data.split("\n")
        for i, line in enumerate(lines):
            if not skip_raw:
                if i:
                    self.raw_lines += 1
                    self.raw_buffer.writeline(line)
                else:
                    self.raw_buffer.write(line)
                if i < len(lines) - 1:
                    self.raw_buffer.newline()
                current_raw_line = self.raw_lines
            else:
                current_raw_line = self.raw_lines - len(lines) + i + 1
            if i < len(lines) - 1:
                maybe_slash_r = "" if line and line[-1] == "\r" else "\r"
                line = f"{line}{maybe_slash_r}\n"
            for buffer in buffers:
                dirty_lines = buffer.write(line)
                if dirty_lines:
                    buffer.raw_to_self[current_raw_line] = dirty_lines[0]
                    for dl in dirty_lines:
                        buffer.self_to_raw[dl] = current_raw_line
            if not skip_raw and self.buffer_lines:
                lined_buffer = self.lined_buffer
                wrapping_buffer = self.wrapping_buffer
                total_lines = lined_buffer.max_line - lined_buffer.min_line + 1
                if total_lines > self.buffer_lines:
                    remove_lined = total_lines - self.buffer_lines
                    lined_buffer.min_line = lined_buffer.remove_lines(remove_lined, lined_buffer.min_line)
                    remove_wrapping = (
                        self.convert_line_number(lined_buffer.min_line, fail_on_error=True) - wrapping_buffer.min_line
                    )
                    wrapping_buffer.min_line = wrapping_buffer.remove_lines(remove_wrapping, wrapping_buffer.min_line)

    @property
    def width(self):
        return self.wrapping_buffer.width

    @width.setter
    def width(self, value):
        self.wrapping_buffer = self._new_wrapping_buffer(value)
        self.write(self.raw_buffer.getvalue(), skip_raw=True, buffers=[self.wrapping_buffer])

    def get_min_line(self, wrap):
        return self._get_buffer(wrap).min_line

    def get_max_line(self, wrap):
        return self._get_buffer(wrap).max_line

    def get_cursor(self, wrap):
        cursor = self._get_buffer(wrap).screen.cursor
        return cursor.x, cursor.y

    def _get_buffer(self, wrap):
        return self.wrapping_buffer if wrap else self.lined_buffer

    def convert_line_number(self, line_number, from_wrapped=False, fail_on_error=False):
        from_buffer = self.wrapping_buffer if from_wrapped else self.lined_buffer
        to_buffer = self.lined_buffer if from_wrapped else self.wrapping_buffer
        raw_line_number = from_buffer.self_to_raw.get(line_number)
        if raw_line_number is None:
            if fail_on_error:
                raise RuntimeError(f"No raw line for line {line_number}")
            else:
                # TODO log warning
                return 0
        to_line_number = to_buffer.raw_to_self.get(raw_line_number)
        if to_line_number is None:
            if fail_on_error:
                raise RuntimeError(f"No to_line for raw_line {raw_line_number} [line={line_number}]")
            else:
                # TODO log warning
                return 0
        return to_line_number
