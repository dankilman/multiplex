import io

from colors import ansilen
from easyansi import screen, cursor, drawing, colors, colors_rgb, attributes
from easyansi._core.codes import CSI


FULL_REFRESH = object()

buffer = io.StringIO()


def prnt(text):
    buffer.write(text)


def flush():
    global buffer
    if not buffer.tell():
        return
    screen.prnt(buffer.getvalue())
    buffer = io.StringIO()


GREEN = colors.GREEN
MAGENTA = colors.MAGENTA
CYAN = colors.CYAN
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


def cached(fn):
    cache = {}

    def wrapper(uid, *args, **kwargs):
        cache_key = (args, kwargs)
        if cache.get(uid) == cache_key:
            return
        fn(*args, **kwargs)
        cache[uid] = cache_key

    wrapper.clear = lambda: cache.clear()

    return wrapper


def clear():
    text_box.clear()
    title.clear()
    status_bar.clear()
    prnt(screen.clear_code())


@cached
def text_box(from_row, to_row, text):
    for line_num in range(to_row, from_row - 1, -1):
        prnt(screen.clear_line_code(line_num))
    prnt(text)


@cached
def title(row, text, cols, hline_color):
    prnt(screen.clear_line_code(row))
    prnt(colors.color_code(hline_color))
    prnt(drawing.hline_code(1))
    prnt(colors.reset_code())
    prnt(text)
    prnt(colors.reset_code())
    offset = 1 + ansilen(text)
    prnt(colors.color_code(hline_color))
    prnt(drawing.hline_code(cols - offset))
    prnt(colors.reset_code())


@cached
def status_bar(row, text, bg):
    prnt(screen.clear_line_code(row))
    r, g, b = bg
    prnt(colors_rgb.color_code(bg_r=r, bg_g=g, bg_b=b))
    prnt(text)
    prnt(colors.reset_code())


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
        help_line.write(colors.reset_code())
        next_line()
        for keys, description in mode_desciptions.items():
            keys_text = ", ".join(str(k) for k in keys)
            line_text = f"{keys_text:<30}{description}"
            help_line.write(line_text)
            next_line()
        next_line()

    help_lines = help_lines[current_line : current_line + lines - 2]
    prnt("".join(help_lines))
