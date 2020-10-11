import asyncio
import logging

import aiostream

from multiplex import ansi
from multiplex import keys
from multiplex import keys_input
from multiplex import resize
from multiplex import commands  # noqa
from multiplex.actions import BoxAction
from multiplex.box import BoxState, TextBox
from multiplex.buffer import Buffer
from multiplex.enums import ViewLocation, BoxLine
from multiplex.exceptions import EndViewer
from multiplex.iterator import to_iterator

logger = logging.getLogger("multiplex.view")

MIN_BOX_HEIGHT = 7


class HelpViewState:
    def __init__(self, viewer):
        self.viewer = viewer
        self.show = False
        self.current_line = 0

    def toggle(self):
        self.show = not self.show
        self.current_line = 0
        return ansi.FULL_REFRESH

    def move_line_up(self):
        self.current_line = max(0, self.current_line - 1)
        return True

    def move_line_down(self):
        self.current_line = min(100, self.current_line + 1)
        return True


class BoxHolder:
    def __init__(self, index, iterator, buffer, state):
        self.id = id(self)
        self.index = index
        self.iterator = iterator
        self.buffer = buffer
        self.state = state
        self.box = None


class Viewer:
    def __init__(self, iterators, box_height=None, verbose=False):
        self.verbose = verbose
        self.holders = [
            BoxHolder(
                index=i,
                iterator=to_iterator(iterator),
                buffer=Buffer(),
                state=BoxState(),
            )
            for i, iterator in enumerate(iterators)
        ]
        self.num_boxes = len(self.holders)
        self.input_reader = keys_input.InputReader(viewer=self, bindings=keys.bindings)
        self.box_height = box_height
        self.current_focused_box = 0
        self.current_view_line = 0
        self.maximized = False
        self.collaped_all = False
        self.wrapped_all = False
        self.help = HelpViewState(self)
        self.cols = None
        self.lines = None

    def swap_indices(self, index1, index2):
        holder1 = self.get_holder(index1)
        holder2 = self.get_holder(index2)
        self.holders[index1] = holder2
        self.holders[index2] = holder1
        holder1.index = index2
        holder2.index = index1
        if self.current_focused_box == index1:
            self.current_focused_box = index2
        elif self.current_focused_box == index2:
            self.current_focused_box = index1

    @property
    def iterators(self):
        return [h.iterator for h in self.holders]

    @property
    def buffers(self):
        return [h.buffer for h in self.holders]

    @property
    def states(self):
        return [h.state for h in self.holders]

    @property
    def boxes(self):
        return [h.box for h in self.holders]

    def get_holder(self, index):
        return self.holders[index]

    def get_buffer(self, index):
        return self.holders[index].buffer

    def get_state(self, index):
        return self.holders[index].state

    def get_iterator(self, index):
        return self.holders[index].iterator

    def get_box(self, index):
        return self.holders[index].box

    def run(self):
        loop = asyncio.get_event_loop()
        try:
            keys_input.setup()
            resize_notifier = resize.setup(loop)
            ansi.setup()
            loop.run_until_complete(self.run_async(resize_notifier))
        except KeyboardInterrupt:
            pass
        finally:
            keys_input.restore()
            resize.restore(loop)
            ansi.restore()

    async def run_async(self, resize_notifier=None):
        loop = asyncio.get_event_loop()
        setup = not resize_notifier
        try:
            if setup:
                keys_input.setup()
                resize_notifier = resize.setup(loop)
                ansi.setup()
            await self._main(resize_notifier)
        except KeyboardInterrupt:
            pass
        finally:
            if setup:
                keys_input.restore()
                resize.restore(loop)
                ansi.restore()

    async def _main(self, resize_notifier):
        self._init()

        async def wrapped_iterator(holder, it):
            async for elem in it:
                yield holder, elem

        iterators = [iterator.iterator for iterator in self.iterators]
        iterators = [wrapped_iterator(self.get_holder(i), it) for i, it in enumerate(iterators)]
        merged = aiostream.stream.merge(*iterators, self.input_reader.read(), resize_notifier)

        async with merged.stream() as streamer:
            async for obj, output in streamer:
                try:
                    self._handle_event(obj, output)
                except EndViewer:
                    return

    def _init(self):
        self._update_lines_cols()
        self.box_height = max(MIN_BOX_HEIGHT, (self.lines - self.num_boxes - 1) // self.num_boxes)
        for holder in self.holders:
            holder.buffer.width = self.cols
            if not holder.state.changed_height:
                holder.state.box_height = self.box_height
            holder.box = TextBox(self, holder)
        self._update_view()

    def _update_lines_cols(self):
        cols, lines = ansi.get_size()
        prev_cols = self.cols
        prev_lines = self.lines
        self.cols = cols
        self.lines = lines
        changed = prev_cols != self.cols or prev_lines != self.lines
        if changed:
            logger.debug(f"sizes: prev [{prev_lines}, {prev_cols}], new [{self.lines}, {self.cols}]")
        return changed

    def _handle_event(self, obj, output):
        if obj is resize.RESIZE:
            ansi.clear()
            self._init()
        elif isinstance(obj, BoxHolder):
            self._update_box(obj.index, output)
            if isinstance(output, BoxAction):
                ansi.clear()
                self._update_view()
        else:
            key_changed = False
            boxes_changed = set()
            full_refresh = False
            for fn in output:
                current_key_changed = self._process_key_handler(fn)
                if current_key_changed is ansi.FULL_REFRESH:
                    full_refresh = True
                    key_changed = True
                elif type(current_key_changed) == int:
                    boxes_changed.add(current_key_changed)
                else:
                    key_changed = key_changed or current_key_changed
            if full_refresh:
                ansi.clear()
            if key_changed:
                self._update_view()
            elif boxes_changed:
                self._update_status_bar()
                for index in boxes_changed:
                    self._update_box(index, data=None)
            else:
                self._update_status_bar()
        ansi.flush()

    def _update_box(self, i, data):
        if data is not None:
            if isinstance(data, BoxAction):
                data.run(self.get_holder(i))
            else:
                self.get_buffer(i).write(data)
        if self.help.show:
            return
        self._update_title_line(i)
        box = self.get_box(i)
        if box.is_visible:
            box.update()

    def _process_key_handler(self, fn):
        prev_current_line = self.current_view_line
        prev_focused_box = self.current_focused_box
        update_view = fn(self)
        if update_view is not None and not isinstance(update_view, bool):
            return update_view
        if prev_focused_box != self.current_focused_box:
            return ansi.FULL_REFRESH
        if prev_current_line != self.current_view_line:
            return ansi.FULL_REFRESH
        return update_view

    def _update_view(self):
        if self.help.show:
            ansi.help_screen(
                current_line=self.help.current_line,
                lines=self.lines,
                cols=self.cols - 1,
                descriptions=keys.descriptions,
            )
        else:
            self._update_status_bar()
            self._update_title_lines()
            self._update_boxes()

    def _update_boxes(self):
        if self.maximized:
            self._update_box(self.current_focused_box, data=None)
        else:
            for i in range(self.num_boxes):
                self._update_box(i, data=None)

    def _update_title_lines(self):
        if self.maximized:
            self._update_title_line(self.current_focused_box)
        else:
            for i in range(self.num_boxes):
                self._update_title_line(i)

    def _update_title_line(self, index):
        screen_y, location = self.get_title_line(index)
        if location != ViewLocation.IN_VIEW:
            return

        iterator = self.get_iterator(index)
        suffix = ""
        if self.verbose:
            box_state = self.get_state(index)
            wrap = box_state.wrap
            auto_scroll = box_state.auto_scroll
            collapsed = box_state.collapsed
            buffer_line = box_state.buffer_start_line
            box_height = box_state.box_height
            state = f"{'W' if wrap else '-'}{'-' if auto_scroll else 'S'}{'C' if collapsed else '-'}"
            state = f"{state} [{buffer_line},{box_height}]"
            suffix = f" [{state}]"
        suffix_len = len(suffix)
        title = iterator.title
        title_len = ansi.ansilen(title)
        hr_space = 4
        _ellipsis = "..."
        if hr_space + title_len + suffix_len > self.cols:
            title = f"{title[:self.cols - suffix_len - len(_ellipsis) - hr_space]}{_ellipsis}"
        text = f" {title}{suffix} "

        logger.debug(f"s{index}:\t{screen_y}\t{location}\t[{self.lines},{self.cols}]")

        ansi.title(
            uid=self.get_holder(index).id,
            row=screen_y,
            text=text,
            hline_color=ansi.CYAN if index == self.current_focused_box else ansi.MAGENTA,
            cols=self.cols,
        )

    def _update_status_bar(self):
        focused = self.focused
        iterator = self.get_iterator(focused.index)
        title = iterator.title
        box_state = focused.state
        wrap = box_state.wrap
        auto_scroll = box_state.auto_scroll

        modes = []
        if not auto_scroll:
            modes.append("SCROLL")
        if self.maximized:
            modes.append("MAXIMIZED")
        if wrap:
            modes.append("WRAP")
        mode = "|".join(modes)
        mode_paren = f"({mode})" if mode else ""

        pending_keys = self.input_reader.pending
        pending_name_parts = []
        while pending_keys:
            cur_offset = len(pending_keys)
            name = None
            while not name and cur_offset:
                name = keys.seq_to_name(pending_keys[:cur_offset], fallback=False)
                if not name:
                    cur_offset -= 1
            pending_name_parts.append(name)
            pending_keys = pending_keys[cur_offset:]

        pending_text = "".join(pending_name_parts)
        if pending_text:
            pending_text = f"{pending_text} "

        title_len = ansi.ansilen(title)
        mode_len = len(mode_paren)
        pending_len = len(pending_text)
        empty = ""
        space_between = self.cols - title_len - mode_len - pending_len
        if space_between < 0:
            title = f"{title[:(self.cols-mode_len) - 4]}... "
            space_between = 0
        text = f"{title}{empty:>{space_between}}{pending_text}{mode_paren}"

        ansi.status_bar(
            uid=-1,
            row=self.get_status_bar_line(),
            text=text,
            bg=ansi.CYAN_RGB if not auto_scroll else ansi.GRAY1_RGB,
        )

    def verify_focused_box_in_view(self):
        if self.maximized:
            return
        screen_y, location = self.get_box_bottom_line(self.current_focused_box)
        if location == ViewLocation.BELOW:
            offset = screen_y
            self.current_view_line += offset
            return
        screen_y, location = self.get_title_line(self.current_focused_box)
        if location == ViewLocation.ABOVE:
            offset = screen_y
            self.current_view_line -= offset
        elif location == ViewLocation.BELOW:
            offset = screen_y
            self.current_view_line += offset

    @property
    def focused(self):
        return self.get_box(self.current_focused_box)

    @property
    def max_current_line(self):
        result = 0
        for state in self.states:
            result += 1
            if not state.collapsed:
                result += state.box_height
        result -= self.get_max_box_line()
        return max(0, result)

    def get_status_bar_line(self):
        return self.lines - 1

    def get_max_box_line(self):
        return self.lines - 2

    def get_title_line(self, index):
        return self._get_box_line(index, BoxLine.TITLE)

    def get_box_top_line(self, index):
        return self._get_box_line(index, BoxLine.TOP)

    def get_box_bottom_line(self, index):
        return self._get_box_line(index, BoxLine.BOTTOM)

    def _get_box_line(self, index, box_line):
        if self.maximized:
            if index != self.current_focused_box:
                return 0, ViewLocation.NOT_FOCUSED
            if box_line == BoxLine.TITLE:
                screen_y = 0
            elif box_line == BoxLine.TOP:
                screen_y = 1
            elif box_line == BoxLine.BOTTOM:
                screen_y = self.get_max_box_line()
            else:
                raise RuntimeError(box_line)
            return screen_y, ViewLocation.IN_VIEW
        else:
            state = self.get_state(index)
            if state.collapsed and box_line != BoxLine.TITLE:
                return 0, ViewLocation.NOT_FOCUSED
            view_y = 0
            for i in range(index):
                # title line
                view_y += 1
                other_state = self.states[i]
                if not other_state.collapsed:
                    view_y += other_state.box_height
            if box_line == BoxLine.TOP:
                view_y += 1
            elif box_line == BoxLine.BOTTOM:
                view_y += state.box_height
            screen_y = view_y - self.current_view_line
            max_line = self.get_max_box_line()
            if screen_y > max_line:
                offest = screen_y - max_line
                return offest, ViewLocation.BELOW
            elif screen_y < 0:
                offset = abs(screen_y)
                return offset, ViewLocation.ABOVE
            else:
                return screen_y, ViewLocation.IN_VIEW
