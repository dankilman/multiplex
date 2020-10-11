import logging

from multiplex import ansi
from multiplex.enums import ViewLocation

logger = logging.getLogger("multiplex.box")


class BoxState:
    def __init__(self):
        self.wrap = True
        self.auto_scroll = True
        self.collapsed = False
        self.buffer_start_line = 0
        self.first_column = 0
        self.view_longest_line = 0
        self.text = None
        self.changed_height = False
        self.box_height = None


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
            uid=self.holder.id,
            from_row=screen_y_1,
            to_row=screen_y_2,
            text=text,
        )

    def update_text(self):
        num_lines = self.num_lines
        if self.state.auto_scroll:
            buffer_num_lines = self.buffer.get_num_lines(self.state.wrap)
            buffer_start_line = max(0, buffer_num_lines - num_lines)
            self.state.buffer_start_line = buffer_start_line
        else:
            buffer_start_line = self.state.buffer_start_line

        cols = self.view.cols
        start_column = self.state.first_column

        lines = self.buffer.get_lines(
            lines=num_lines,
            start_line=buffer_start_line,
            columns=cols,
            start_column=start_column,
            wrap=self.state.wrap,
        )
        self.state.text = "\n".join(line for _, line in lines)
        if not self.state.wrap:
            self.state.view_longest_line = max(line_length for line_length, _ in lines)

    def move_line_up(self):
        self.state.buffer_start_line = max(0, self.state.buffer_start_line - 1)
        return self.index

    def move_line_down(self):
        buffer_lines = self.buffer.get_num_lines(self.state.wrap)
        max_start_line = buffer_lines - self.num_lines
        self.state.buffer_start_line = max(0, min(max_start_line, self.state.buffer_start_line + 1))
        return self.index

    def move_all_up(self):
        self.state.buffer_start_line = 0
        return self.index

    def move_all_down(self):
        self.state.buffer_start_line = self.max_start_line
        return self.index

    def move_page_up(self):
        self.state.buffer_start_line = max(0, self.state.buffer_start_line - self.num_lines)
        return self.index

    def move_page_down(self):
        self.state.buffer_start_line = min(self.max_start_line, self.state.buffer_start_line + self.num_lines)
        return self.index

    def move_half_page_up(self):
        self.state.buffer_start_line = max(0, self.state.buffer_start_line - self.num_lines // 2)
        return self.index

    def move_half_page_down(self):
        self.state.buffer_start_line = min(self.max_start_line, self.state.buffer_start_line + self.num_lines // 2)
        return self.index

    def move_right(self):
        state = self.state
        if not state.wrap:
            state.first_column = min(state.first_column + 1, self.max_first_column)
            return self.index
        return False

    def move_left(self):
        state = self.state
        if not state.wrap:
            state.first_column = max(0, state.first_column - 1)
            return self.index
        return False

    def move_right_until_end(self):
        state = self.state
        if not state.wrap:
            state.first_column = self.max_first_column
            return self.index
        return False

    def move_left_until_start(self):
        state = self.state
        if not state.wrap:
            state.first_column = 0
            return self.index
        return False

    def increase_box_height(self):
        self.state.box_height = min(self.view.get_max_box_line(), self.state.box_height + 1)
        self.state.changed_height = True
        return True

    def decrease_box_height(self):
        self.state.box_height = max(1, self.state.box_height - 1)
        self.state.changed_height = True
        return ansi.FULL_REFRESH

    def toggle_auto_scroll(self):
        self.state.auto_scroll = not self.state.auto_scroll
        return True

    def toggle_wrap(self, value=None):
        if value is not None:
            wrap = value
        else:
            wrap = self.state.wrap
        self.state.first_column = 0
        self.state.wrap = not wrap
        if not self.state.auto_scroll:
            line = self.state.buffer_start_line
            result = self.buffer.convert_line_number(line, from_wrapped=wrap)
            if result is None:
                logger.warning(f"No mathing line for conversion wrap: {wrap}, line: {line}")
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

    @property
    def num_lines(self):
        return self.view.get_max_box_line() if self.is_maximized else self.state.box_height

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
    def max_start_line(self):
        buffer_lines = self.buffer.get_num_lines(self.state.wrap)
        return buffer_lines - self.num_lines
