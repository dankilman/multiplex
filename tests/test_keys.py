import pytest

from multiplex.keys import generic_key_to_name, seq_to_name, HOME, is_multi, key_to_seq, bind


def test_generic_key_to_name_printable():
    assert generic_key_to_name(ord("k")) == "k"


def test_generic_key_to_name_non_printable():
    assert generic_key_to_name(20) == "[20]"


def test_seq_to_name_list_input():
    assert seq_to_name([ord("k")]) == "k"


def test_seq_to_name_ctrl_name():
    assert seq_to_name((11,)) == "^K"


def test_seq_to_name_predefined():
    assert seq_to_name(HOME) == "Home"


def test_seq_to_name_single_char():
    assert seq_to_name((ord("k"),)) == "k"


def test_seq_to_name_fallback():
    assert seq_to_name((ord("k"), 20)) == "k[20]"


def test_seq_to_name_no_fallback():
    assert seq_to_name((ord("k"), 20), fallback=False) is None


def test_is_multi():
    assert not is_multi((11,))
    assert not is_multi((11, 12))
    assert not is_multi([11, 12])
    assert is_multi([[11], [12]])
    assert is_multi([(11,), (12,)])
    assert is_multi(["one", "two"])


def test_key_to_seq_str_input():
    assert key_to_seq("abc") == (ord("a"), ord("b"), ord("c"))


def test_key_to_seq_multi_input():
    assert key_to_seq(["gg", (11,)]) == (ord("g"), ord("g"), 11)


def test_key_to_seq_standard_input():
    assert key_to_seq([1, 2, 3]) == (1, 2, 3)
    assert key_to_seq((1, 2, 3)) == (1, 2, 3)


def test_key_to_seq_invalid_input():
    with pytest.raises(RuntimeError):
        key_to_seq(True)


def test_bind_basic():
    mode = "a"
    bindings = {mode: {}}
    descriptions = {mode: {}}

    @bind(mode, "a", "b", description="c", custom_bindings=bindings, custom_descriptions=descriptions)
    def fn1():
        pass

    assert bindings[mode][(ord("a"),)] is fn1
    assert bindings[mode][(ord("b"),)] is fn1
    assert descriptions[mode][("a", "b")] == "c"


def test_bind_description_fallback():
    mode = "a"
    bindings = {mode: {}}
    descriptions = {mode: {}}

    @bind(mode, "a", custom_bindings=bindings, custom_descriptions=descriptions)
    def fn1():
        pass

    assert descriptions[mode][("a",)] == "fn1"


def test_bind_multi_description():
    mode = "a"
    bindings = {mode: {}}
    descriptions = {mode: {}}

    @bind(mode, ["a", "b"], custom_bindings=bindings, custom_descriptions=descriptions)
    def fn1():
        pass

    assert descriptions[mode][("ab",)] == "fn1"


def test_bind_seq_to_name_description():
    mode = "a"
    bindings = {mode: {}}
    descriptions = {mode: {}}

    @bind(mode, ["a", (27,)], custom_bindings=bindings, custom_descriptions=descriptions)
    def fn1():
        pass

    assert descriptions[mode][("aEsc",)] == "fn1"
