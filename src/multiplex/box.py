import logging

from multiplex import ansi
from multiplex.buffer import Buffer
from multiplex.enums import ViewLocation

logger = logging.getLogger("multiplex.box")


class BoxHolder:
    def __init__(self, index, iterator, box_height, viewer):
        self.id = id(self)
        self.index = index
        self.iterator = iterator
        self.buffer = Buffer(buffer_lines=viewer.buffer_lines)
        self.state = BoxState(box_height)
        self.box = TextBox(viewer, self)


class BoxState:
    def __init__(self, box_height):
        self.wrap = True
        self.auto_scroll = True
        self.input_mode = False
        self.stream_done = False
        self.collapsed = False
        self.buffer_start_line = 0
        self.first_column = 0
        self.view_longest_line = 0
        self.text = None
        self.changed_height = box_height is not None
        self.box_height = box_height


class TextBox:
    def __init__(self, view, holder):
        self.view = view
        self.holder = holder
        self.buffer = self.holder.buffer
        self.state = self.holder.state

    @property
    def index(self):
        return self.holder.index

    def update(self):
        self.update_text()

        screen_y_1, location_1 = self.view.get_box_top_line(self.index)
        screen_y_2, location_2 = self.view.get_box_bottom_line(self.index)

        text = self.state.text

        if location_1 == ViewLocation.ABOVE:
            text = "\n".join(text.split("\n")[screen_y_1:])
            screen_y_1 = 0
        if location_2 == ViewLocation.BELOW:
            text = "\n".join(text.split("\n")[:-screen_y_2])
            screen_y_2 = self.view.get_max_box_line()

        logger.debug(
            f"{self.index}:"
            f"\t{screen_y_1}"
            f"\t{screen_y_2}"
            f"\t{location_1}"
            f"\t{location_2}"
            f"\t[{self.view.lines},{self.view.cols}]"
        )

        ansi.text_box(
            from_row=screen_y_1,
            to_row=screen_y_2,
            text=text,
        )

    def update_text(self):
        if self.state.auto_scroll and not self.state.stream_done:
            self.state.buffer_start_line = self.max_start_line
        lines = self.buffer.get_lines(
            lines=self.num_view_lines,
            start_line=self.state.buffer_start_line,
            columns=self.view.cols,
            start_column=self.state.first_column,
            wrap=self.state.wrap,
        )
        self.state.text = "\n".join(line for _, line in lines)
        if not self.state.wrap:
            value = max(line_length for line_length, _ in lines) if lines else 0
            self.state.view_longest_line = value

    def move_line_up(self):
        return self.set_minmax_up_motion(self.state.buffer_start_line - 1)

    def move_line_down(self):
        return self.set_minmax_down_motion(self.state.buffer_start_line + 1)

    def move_page_up(self):
        return self.set_minmax_up_motion(self.state.buffer_start_line - self.num_view_lines)

    def move_page_down(self):
        return self.set_minmax_down_motion(self.state.buffer_start_line + self.num_view_lines)

    def move_half_page_up(self):
        return self.set_minmax_up_motion(self.state.buffer_start_line - self.num_view_lines // 2)

    def move_half_page_down(self):
        return self.set_minmax_down_motion(self.state.buffer_start_line + self.num_view_lines // 2)

    def move_all_up(self):
        self.state.buffer_start_line = self.min_start_line
        return self.index

    def move_all_down(self):
        self.state.buffer_start_line = self.max_start_line
        return self.index

    def move_right(self):
        state = self.state
        if state.wrap:
            return False
        state.first_column = min(state.first_column + 1, self.max_first_column)
        return self.index

    def move_left(self):
        state = self.state
        if state.wrap:
            return False
        state.first_column = max(0, state.first_column - 1)
        return self.index

    def move_half_screen_right(self):
        state = self.state
        if state.wrap:
            return False
        state.first_column = min(state.first_column + self.view.cols // 2, self.max_first_column)
        return self.index

    def move_half_screen_left(self):
        state = self.state
        if state.wrap:
            return False
        state.first_column = max(0, state.first_column - self.view.cols // 2)
        return self.index

    def move_right_until_end(self):
        state = self.state
        if state.wrap:
            return False
        state.first_column = self.max_first_column
        return self.index

    def move_left_until_start(self):
        state = self.state
        if state.wrap:
            return False
        state.first_column = 0
        return self.index

    def increase_box_height(self):
        self.state.box_height = min(self.view.get_max_box_line(), self.state.box_height + 1)
        self.state.changed_height = True
        return True

    def decrease_box_height(self):
        self.state.box_height = max(0, self.state.box_height - 1)
        self.state.changed_height = True
        return ansi.FULL_REFRESH

    def toggle_auto_scroll(self):
        self.state.auto_scroll = not self.state.auto_scroll
        return True

    def activate_input_mode(self):
        self.state.input_mode = True
        ansi.show_cursor()
        return True

    def exit_input_mode(self):
        self.state.input_mode = False
        ansi.hide_cursor()
        return True

    def toggle_wrap(self, value=None):
        initial_value = self.state.wrap
        new_value = value if value is not None else not initial_value
        if initial_value == new_value:
            return False
        self.state.first_column = 0
        self.state.wrap = new_value
        if not self.state.auto_scroll or self.state.stream_done:
            line = self.state.buffer_start_line
            result = self.buffer.convert_line_number(line, from_wrapped=initial_value)
            if result is None:
                logger.warning(f"No mathing line for conversion wrap: {new_value}, line: {line}")
                result = 0
            self.state.buffer_start_line = result
        return True

    def toggle_collapse(self, value=None):
        if value is not None:
            collapsed = value
        else:
            collapsed = not self.state.collapsed
        self.state.collapsed = collapsed
        return ansi.FULL_REFRESH if collapsed else True

    def strip_empty_lines(self, include_not_stream_done=False):
        if not include_not_stream_done and not self.state.stream_done:
            return
        self.state.box_height = min(self.state.box_height, self.num_buffer_lines)

    @property
    def num_view_lines(self):
        return self.view.lines - 1 if self.is_maximized else self.state.box_height

    @property
    def is_focused(self):
        return self.index == self.view.current_focused_box

    @property
    def is_visible(self):
        if self.view.maximized and not self.is_focused:
            return False
        if self.state.collapsed and not self.is_maximized:
            return False
        _, location = self.view.get_box_top_line(self.index)
        if location == ViewLocation.BELOW:
            return False
        _, location = self.view.get_box_bottom_line(self.index)
        if location == ViewLocation.ABOVE:
            return False
        return True

    @property
    def is_maximized(self):
        return self.view.maximized and self.is_focused

    @property
    def max_first_column(self):
        return max(0, self.state.view_longest_line - self.view.cols)

    @property
    def num_buffer_lines(self):
        buffer_min_line = self.buffer.get_min_line(self.state.wrap)
        buffer_max_line = self.buffer.get_max_line(self.state.wrap)
        return buffer_max_line - buffer_min_line + 1

    @property
    def min_start_line(self):
        return self.buffer.get_min_line(self.state.wrap)

    @property
    def max_start_line(self):
        buffer_min_line = self.buffer.get_min_line(self.state.wrap)
        buffer_max_line = self.buffer.get_max_line(self.state.wrap)
        return max(buffer_min_line, buffer_max_line - self.num_view_lines + 1)

    def set_minmax_down_motion(self, value):
        return self._set_min_max_motion(value, self.state.buffer_start_line)

    def set_minmax_up_motion(self, value):
        return self._set_min_max_motion(value, self.min_start_line)

    def set_width(self, width):
        raw_line = self.buffer.wrapping_buffer.self_to_raw.get(self.state.buffer_start_line, 0)
        self.buffer.width = width
        if self.state.wrap and (not self.state.auto_scroll or self.state.stream_done):
            self.state.buffer_start_line = self.buffer.wrapping_buffer.raw_to_self[raw_line]

    def _set_min_max_motion(self, value, min_value):
        self.state.buffer_start_line = max(min_value, min(self.max_start_line, value))
        return self.index
