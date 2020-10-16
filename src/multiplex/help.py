from multiplex import keys, ansi


class HelpViewState:
    def __init__(self, viewer):
        self.viewer = viewer
        self.show = False
        self.current_line = 0
        self.max_current_line = (
            2  # box lines
            + len(keys.descriptions) * 2
            - 1  # last description new line
            + sum(len(mode_desc) for mode_desc in keys.descriptions.values())
        )

    def toggle(self):
        self.show = not self.show
        self.current_line = 0
        return ansi.FULL_REFRESH

    def move_line_up(self):
        self.current_line = max(0, self.current_line - 1)
        return True

    def move_line_down(self):
        max_line = self.max_current_line
        if self.viewer.lines:
            max_line -= self.viewer.lines
        self.current_line = max(0, min(max_line, self.current_line + 1))
        return True
