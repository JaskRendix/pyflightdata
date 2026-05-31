from pyarinc.utils.bitops import bits_from_bytes, extract_bits, int_from_bits


def test_bits_and_int():
    data = b"\xA5"  # 10100101
    bits = list(bits_from_bytes(data))
    assert bits == [1, 0, 1, 0, 0, 1, 0, 1]
    assert int_from_bits(bits) == 0xA5


def test_slice_bits():
    data = b"\xFF\x00"  # 11111111 00000000
    # extract first 8 bits
    assert extract_bits(data, 0, 8) == 0xFF
    # extract next 8 bits
    assert extract_bits(data, 8, 8) == 0x00
    # signed extraction: two's complement of 0xFF (8 bits) -> -1
    assert extract_bits(b"\xFF", 0, 8, signed=True) == -1
