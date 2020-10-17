from multiplex.buffer import Buffer


def test_buffer_kitchen():
    width = 5
    buffer = Buffer(width)
    assert buffer.width == width
    text = "123456789"
    buffer.write(text)
    assert buffer.num_lines == 1
    assert buffer.wrapped_num_lines == 2
    assert buffer.get_num_lines(wrap=False) == 1
    assert buffer.get_num_lines(wrap=True) == 2
    assert buffer.get_lines(1, 0, width, 0, wrap=False) == [(9, "12345")]
    assert buffer.get_lines(1, 0, width, 0, wrap=True) == [(5, "12345")]
    assert buffer.get_lines(2, 0, width, 0, wrap=False) == [(9, "12345"), (0, " " * 5)]
    assert buffer.get_lines(2, 0, width, 0, wrap=True) == [(5, "12345"), (4, "6789 ")]
    assert buffer.get_lines(1, 1, width, 0, wrap=True) == [(4, "6789 ")]
    assert buffer.get_lines(1, 0, width, 3, wrap=False) == [(9, "45678")]

    width = 3
    buffer.width = width
    assert buffer.num_lines == 1
    assert buffer.wrapped_num_lines == 3
    assert buffer.get_lines(1, 0, width, 0, wrap=False) == [(9, "123")]
    assert buffer.get_lines(3, 0, width, 0, wrap=True) == [(3, "123"), (3, "456"), (3, "789")]

    assert buffer.raw_buffer.getvalue() == text
    assert buffer.raw_buffer.tell() == len(text)

    buffer.write("\nabcd")
    assert buffer.convert_line_number(0, from_wrapped=False) == 0
    assert buffer.convert_line_number(1, from_wrapped=False) == 3
    assert buffer.convert_line_number(0, from_wrapped=True) == 0
    assert buffer.convert_line_number(2, from_wrapped=True) == 0
    assert buffer.convert_line_number(3, from_wrapped=True) == 1
    assert buffer.convert_line_number(4, from_wrapped=True) == 1
