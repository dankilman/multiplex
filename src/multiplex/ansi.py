import io

from easyansi import screen, cursor, drawing, colors, colors_rgb, attributes
from easyansi._core.codes import CSI


FULL_REFRESH = object()

buffer = io.StringIO()


def prnt(text):
    buffer.write(str(text))


def flush():
    global buffer
    if not buffer.tell():
        return
    screen.prnt(buffer.getvalue())
    buffer = io.StringIO()


NONE = object()
RESET = colors_rgb.reset_code()

MAGENTA = colors.MAGENTA
CYAN = colors.CYAN
RED_RGB = (255, 0, 0)
GREEN_RGB = (0, 255, 0)
GRAY1_RGB = (51, 51, 51)
CYAN_RGB = (0, 200, 200)


CLEAR_LINE = CSI + "2K"
ENABLE_ALT_BUFFER = CSI + "?1049h"
DISABLE_ALT_BUFFER = CSI + "?1049l"


def setup():
    screen.prnt(ENABLE_ALT_BUFFER)
    cursor.hide()


def restore():
    global buffer
    clear()
    buffer = io.StringIO()
    cursor.show()
    screen.clear()
    screen.prnt(DISABLE_ALT_BUFFER)


def get_size():
    return screen.get_size()


def clear():
    prnt(screen.clear_code())


def text_box(from_row, to_row, text):
    for line_num in range(to_row, from_row - 1, -1):
        prnt(screen.clear_line_code(line_num))
    prnt(text)


def title(row, text, cols, hline_color):
    prnt(screen.clear_line_code(row))
    prnt(colors.color_code(hline_color))
    prnt(drawing.hline_code(1))
    prnt(RESET)
    prnt(text)
    prnt(RESET)
    offset = 1 + len(text)
    prnt(colors.color_code(hline_color))
    prnt(drawing.hline_code(cols - offset))
    prnt(RESET)


def status_bar(row, text):
    prnt(screen.clear_line_code(row))
    prnt(text)
    prnt(RESET)


def help_screen(current_line, lines, cols, descriptions):
    prnt(screen.clear_code())
    prnt(drawing.box_code(width=cols, height=lines))
    prnt(cursor.locate_code(2, 1))

    help_lines = []
    help_line = io.StringIO()

    def next_line():
        nonlocal help_line
        help_line.write(cursor.next_line_code())
        help_line.write(cursor.right_code(2))
        help_lines.append(help_line.getvalue())
        help_line = io.StringIO()

    for mode, mode_desciptions in descriptions.items():
        help_line.write(attributes.bright_code())
        help_line.write(colors.color_code(colors.MAGENTA))
        help_line.write(mode.capitalize())
        help_line.write(RESET)
        next_line()
        for keys, description in mode_desciptions.items():
            keys_text = ", ".join(str(k) for k in keys)
            line_text = f"{keys_text:<30}{description}"
            help_line.write(line_text)
            next_line()
        next_line()

    help_lines = help_lines[current_line : current_line + lines - 2]
    prnt("".join(help_lines))


class C:
    def __init__(self, *args, fg=None, bg=None):
        self.fg = fg
        self.bg = bg
        self.parts = []
        for part in args:
            self._add(part)

    def copy(self):
        parts = [p.copy() if isinstance(p, C) else p for p in self.parts]
        return self.__class__(*parts, fg=self.fg, bg=self.bg)

    def __len__(self):
        return sum(len(p) for p in self.parts)

    def __str__(self):
        fg, bg = self.fg, self.bg
        style = None
        if fg is NONE and bg is NONE:
            style = RESET
            fg, bg = None, None
        elif fg is NONE:
            fg = (255, 255, 255)
        elif bg is NONE:
            bg = (0, 0, 0)

        if fg or bg:
            style = colors_rgb.color_code(
                *(fg or (None, None, None)),
                *(bg or (None, None, None)),
            )
        result = io.StringIO()
        if style:
            result.write(style)
        for part in self.parts:
            result.write(str(part))
            if isinstance(part, C) and style:
                result.write(style)
        return result.getvalue()

    def __iadd__(self, other):
        self._add(other)
        return self

    def __getitem__(self, item):
        assert isinstance(item, slice)
        assert not item.start
        assert not item.step
        size = item.stop
        result = self.copy()
        result._truncate(size)
        return result

    def _truncate(self, size):
        new_parts = []
        for part in self.parts:
            part_len = len(part)
            if part_len <= size:
                new_parts.append(part)
                size -= part_len
            else:
                new_parts.append(part[:size])
                break
        self.parts = new_parts

    def _add(self, part):
        if isinstance(part, C):
            part = part.copy()
            if not part.fg:
                part.fg = self.fg
            if not part.bg:
                part.bg = self.bg
        self.parts.append(part)
