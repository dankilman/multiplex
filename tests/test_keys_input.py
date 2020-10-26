from contextlib import contextmanager
from functools import partial
from unittest import mock
from unittest.mock import Mock

from multiplex.keys import bind as _bind, HELP, SCROLL, NORMAL, GLOBAL, INPUT
from multiplex.keys_input import InputReader


def _test_set(show_help=False, auto_scroll=True, input_mode=False):
    bindings = {GLOBAL: {}, NORMAL: {}, HELP: {}, SCROLL: {}, INPUT: {}}
    descriptions = {GLOBAL: {}, NORMAL: {}, HELP: {}, SCROLL: {}, INPUT: {}}
    bind = partial(_bind, custom_bindings=bindings, custom_descriptions=descriptions)
    viewer = MockViewer(show_help, auto_scroll, input_mode)
    return bind, InputReader(viewer, bindings)


class MockViewer:
    def __init__(self, show_help=False, auto_scroll=True, input_mode=False):
        self.help = MockHelp(show_help)
        self.is_input_mode = input_mode
        self.is_scrolling = not auto_scroll


class MockHelp:
    def __init__(self, show=False):
        self.show = show


class MockBox:
    def __init__(self, auto_scroll):
        self.state = MockBoxState(auto_scroll)
        pass


class MockBoxState:
    def __init__(self, auto_scroll):
        self.auto_scroll = auto_scroll


def _test_process_single_found_sequence(mode):
    show_help = mode == HELP
    auto_scroll = mode != SCROLL
    input_mode = mode == INPUT
    bind, reader = _test_set(show_help, auto_scroll, input_mode)

    @bind(mode, "a")
    def fn1():
        pass

    expected = [fn1]

    if mode != GLOBAL:

        @bind(GLOBAL, "a")
        def fn2():
            pass

        @bind(GLOBAL, "b")
        def fn3():
            pass

        if mode != INPUT:
            expected.append(fn3)

    assert reader._process([ord("a"), ord("b")]) == (expected, [])


def test_process_single_found_sequence_normal():
    _test_process_single_found_sequence(NORMAL)


def test_process_single_found_sequence_scroll():
    _test_process_single_found_sequence(SCROLL)


def test_process_single_found_sequence_input():
    _test_process_single_found_sequence(INPUT)


def test_process_single_found_sequence_help():
    _test_process_single_found_sequence(HELP)


def test_process_single_found_sequence_global():
    _test_process_single_found_sequence(GLOBAL)


def test_process_pending():
    bind, reader = _test_set()

    @bind(NORMAL, "ab")
    def fn1():
        pass

    keys1 = [ord("a")]
    keys2 = [ord("a"), ord("b")]
    keys3 = [ord("a"), ord("c"), ord("d")]
    assert reader._process(keys1) == ([], keys1)
    assert reader._process(keys2) == ([fn1], [])
    assert reader._process(keys3) == ([], [])

    @bind(NORMAL, "def")
    def fn2():
        pass

    keys1 = [ord("d")]
    keys2 = [ord("d"), ord("b")]
    keys3 = [ord("d"), ord("e")]
    assert reader._process(keys1) == ([], keys1)
    assert reader._process(keys2) == ([], [])
    assert reader._process(keys3) == ([], keys3)


def test_process_more_than_one_sequence():
    bind, reader = _test_set()

    @bind(NORMAL, "ab")
    def fn1():
        pass

    @bind(NORMAL, "cd")
    def fn2():
        pass

    keys1 = [ord("a"), ord("b"), ord("a")]
    keys2 = [ord("a"), ord("b"), ord("a"), ord("b")]
    keys3 = [ord("a"), ord("b"), ord("c"), ord("d")]
    assert reader._process(keys1) == ([fn1], keys1[2:])
    assert reader._process(keys2) == ([fn1, fn1], [])
    assert reader._process(keys3) == ([fn1, fn2], [])


@contextmanager
def patch_read(data=None, read=None):
    mock_has_data = Mock()
    mock_has_data.side_effect = data or [False]
    mock_read = Mock()
    mock_read.side_effect = read or []
    with mock.patch("sys.stdin.fileno", Mock()):
        with mock.patch("os.read", mock_read):
            with mock.patch("multiplex.keys_input._has_data", mock_has_data):
                yield


def test_read_iteration_no_data():
    bind, reader = _test_set()
    assert reader.pending == []
    with patch_read(data=[False]):
        assert reader._read_iteration() is None
    assert reader.pending == []


def test_read_iteration_process_one():
    bind, reader = _test_set()

    @bind(NORMAL, "a")
    def fn1():
        pass

    with patch_read(data=[True, True, False], read=["a"]):
        assert reader._read_iteration() == [fn1]

    assert reader.pending == []


def test_read_iteration_has_pending():
    bind, reader = _test_set()

    @bind(NORMAL, "ab")
    def fn1():
        pass

    with patch_read(data=[True, True, False], read=["a"]):
        assert reader._read_iteration() == []

    assert reader.pending == [ord("a")]


def test_read_iteration_backspace_and_delete():
    bind, reader = _test_set()

    @bind(NORMAL, "abcdef")
    def fn1():
        pass

    with patch_read(data=[True, True, True, True, True, True, True, True], read=["a", "b", "c", chr(8), chr(127)]):
        assert reader._read_iteration() == []
        assert reader.pending == [ord("a"), ord("b")]
        assert reader._read_iteration() == []
        assert reader.pending == [ord("a")]
