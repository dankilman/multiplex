from multiplex.keys import *

from .exceptions import EndViewer

from .ansi import FULL_REFRESH


# toggles
@bind(GLOBAL, "s", description="Toggle auto-scoll/manual-scroll for currently focused box")
def toggle_auto_scroll(viewer):
    return viewer.focused.toggle_auto_scroll()


@bind(GLOBAL, "w", description="Toggle wrap/unwrap for currently focused box")
def toggle_wrap(viewer):
    return viewer.focused.toggle_wrap()


@bind(GLOBAL, "W", description="Toggle wrap/unwrap for all boxes")
def toggle_wrap_all(viewer):
    new_value = not viewer.wrapped_all
    for box in viewer.boxes:
        box.toggle_wrap(new_value)
    viewer.wrapped_all = new_value
    viewer.verify_focused_box_in_view()
    return FULL_REFRESH


@bind(GLOBAL, "c", description="Toggle expand/collapse for currently focused box")
def toggle_collapse(viewer):
    return viewer.focused.toggle_collapse()


@bind(GLOBAL, "C", description="Toggle expand/collapse for all boxes")
def toggle_collapse_all(viewer):
    new_value = not viewer.collaped_all
    for box in viewer.boxes:
        box.toggle_collapse(new_value)
    viewer.collaped_all = new_value
    viewer.verify_focused_box_in_view()
    return FULL_REFRESH


@bind(GLOBAL, "m", description="Toggle maxmize")
def toggle_maximize(viewer):
    viewer.maximized = not viewer.maximized
    return FULL_REFRESH


@bind(GLOBAL, "?", description="Show/hide this help screen")
def toggle_help(viewer):
    return viewer.help.toggle()


# quit
@bind(GLOBAL, "q", description="Quit")
def end(*_):
    raise EndViewer


# global inside box movement
@bind(GLOBAL, "l", RIGHT, description="Move 1 char right")
def move_right(viewer):
    return viewer.focused.move_right()


@bind(GLOBAL, "h", LEFT, description="Move 1 char left")
def move_left(viewer):
    return viewer.focused.move_left()


@bind(GLOBAL, "$", description="Move all the way to the right")
def move_right_until_end(viewer):
    return viewer.focused.move_right_until_end()


@bind(GLOBAL, "_", "0", description="Move all the way to the left")
def move_left_until_start(viewer):
    return viewer.focused.move_left_until_start()


# main mode
@bind(NORMAL, "j", DOWN, description="Focus next box")
def next_box(viewer):
    viewer.current_focused_box = min(viewer.current_focused_box + 1, viewer.num_boxes - 1)
    viewer.verify_focused_box_in_view()


@bind(NORMAL, "k", UP, description="Focus previous box")
def previous_box(viewer):
    viewer.current_focused_box = max(viewer.current_focused_box - 1, 0)
    viewer.verify_focused_box_in_view()


@bind(NORMAL, ALT_J, ALT_DOWN, description="Switch places with box below")
def switch_with_next_box(viewer):
    if viewer.current_focused_box + 1 >= viewer.num_boxes:
        return False
    viewer.swap_indices(viewer.current_focused_box, viewer.current_focused_box + 1)
    viewer.verify_focused_box_in_view()
    return FULL_REFRESH


@bind(NORMAL, ALT_K, ALT_UP, description="Switch places with box above")
def switch_with_previous_box(viewer):
    if viewer.current_focused_box - 1 < 0:
        return False
    viewer.swap_indices(viewer.current_focused_box, viewer.current_focused_box - 1)
    viewer.verify_focused_box_in_view()
    return FULL_REFRESH


@bind(NORMAL, "gg", HOME, description="Focus first box")
def all_up(viewer):
    viewer.current_focused_box = 0
    viewer.verify_focused_box_in_view()


@bind(NORMAL, "G", END, description="Focus last box")
def all_down(viewer):
    viewer.current_focused_box = viewer.num_boxes - 1
    viewer.verify_focused_box_in_view()


@bind(NORMAL, CTRL_F, PAGEDOWN, description="View 1 page down")
def page_down(viewer):
    viewer.current_view_line = min(viewer.max_current_line, viewer.current_view_line + viewer.lines)


@bind(NORMAL, CTRL_B, PAGEUP, description="View 1 page up")
def page_up(viewer):
    viewer.current_view_line = max(0, viewer.current_view_line - viewer.lines)


@bind(NORMAL, CTRL_D, description="View 1/2 page down")
def half_page_down(viewer):
    viewer.current_view_line = min(viewer.max_current_line, viewer.current_view_line + viewer.lines // 2)


@bind(NORMAL, CTRL_U, description="View 1/2 page up")
def half_page_up(viewer):
    viewer.current_view_line = max(0, viewer.current_view_line - viewer.lines // 2)


@bind(NORMAL, CTRL_J, description="View 1 line down")
def line_down(viewer):
    viewer.current_view_line = min(viewer.max_current_line, viewer.current_view_line + 1)


@bind(NORMAL, CTRL_K, description="View 1 line up")
def line_up(viewer):
    viewer.current_view_line = max(0, viewer.current_view_line - 1)


# change box height
@bind(GLOBAL, ">", description="Increase box height")
def increase_box_height(viewer):
    return viewer.focused.increase_box_height()


@bind(GLOBAL, "<", description="Decrease box height")
def decrease_box_height(viewer):
    return viewer.focused.decrease_box_height()


# scroll mode
@bind(SCROLL, "j", DOWN, description="Scroll 1 line down")
def move_line_down(viewer):
    return viewer.focused.move_line_down()


@bind(SCROLL, "k", UP, description="Scroll 1 line up")
def move_line_up(viewer):
    return viewer.focused.move_line_up()


@bind(SCROLL, "gg", HOME, description="Scroll to start")
def move_all_up(viewer):
    return viewer.focused.move_all_up()


@bind(SCROLL, "G", END, description="Scroll to end")
def move_all_down(viewer):
    return viewer.focused.move_all_down()


@bind(SCROLL, CTRL_B, PAGEUP, description="Scroll 1 page up")
def move_page_up(viewer):
    return viewer.focused.move_page_up()


@bind(SCROLL, CTRL_F, PAGEDOWN, description="Scroll 1 page down")
def move_page_down(viewer):
    return viewer.focused.move_page_down()


@bind(SCROLL, CTRL_U, description="Scroll 1/2 page up")
def move_half_page_up(viewer):
    return viewer.focused.move_half_page_up()


@bind(SCROLL, CTRL_D, description="Scroll 1/2 page down")
def move_half_page_down(viewer):
    return viewer.focused.move_half_page_down()


# help mode
@bind(HELP, "j", DOWN, description="Scroll 1 line down [in help screen]")
def move_line_down(viewer):
    return viewer.help.move_line_down()


@bind(HELP, "k", UP, description="Scroll 1 line up [in help screen]")
def move_line_up(viewer):
    return viewer.help.move_line_up()
