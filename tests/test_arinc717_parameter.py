import pytest

from pyarinc.models.parameter import Parameter


@pytest.mark.parametrize(
    "frame_bytes,start,bitlen,expected",
    [
        (b"\x0F\xF0", 0, 8, 0x0F),  # first byte
        (b"\x0F\xF0", 8, 8, 0xF0),  # second byte
        (b"\xF0\x0F", 4, 8, 0x00),  # cross-byte
    ],
)
def test_arinc717_extract_bits(frame_bytes, start, bitlen, expected):
    p = Parameter("X", start_bit=start, bit_length=bitlen, data_type="DISCRETE")
    assert p.extract_bits_767(frame_bytes, start, bitlen) == expected


def test_arinc717_absolute_bit_start():
    # subframe=1, word=2, bit_offset=3
    # words_per_subframe=4, word_bits=12 → subframe=48 bits, word=24 bits
    p = Parameter(
        "ALT",
        start_bit=0,
        bit_length=8,
        data_type="BNR",
        subframe=1,
        word=2,
        bit_offset=3,
    )
    assert p.compute_absolute_bit_start(4, 12) == 48 + 24 + 3


def test_arinc717_decode_from_frame_bnr_unsigned():
    frame = bytes([0x12, 0x34])
    p = Parameter("ALT", start_bit=0, bit_length=16, data_type="BNR")
    val, valid = p.decode_from_frame(frame, 4, 12)
    assert valid
    assert val == 0x1234


def test_arinc717_decode_from_frame_bnr_signed():
    frame = bytes([0xFF])  # -1 in 8-bit signed
    p = Parameter("TEMP", start_bit=0, bit_length=8, data_type="BNR", signed=True)
    val, valid = p.decode_from_frame(frame, 4, 12)
    assert valid
    assert val == -1


@pytest.mark.parametrize(
    "raw,expected",
    [
        (0x12, "12"),
        (0x123, "123"),
        (0x0, "0"),
    ],
)
def test_arinc717_bcd(raw, expected):
    p = Parameter("BCD", start_bit=0, bit_length=12, data_type="BCD")
    assert p.decode(raw) == expected


def test_arinc717_discrete():
    p1 = Parameter("D1", start_bit=0, bit_length=1, data_type="DISCRETE")
    assert p1.decode(1) is True
    p2 = Parameter("D2", start_bit=0, bit_length=3, data_type="DISCRETE")
    assert p2.decode(0b101) == 5


def test_arinc717_char():
    p = Parameter("CH", start_bit=0, bit_length=16, data_type="CHAR")
    assert p.decode(0x4142) == "AB"


def test_arinc717_utc():
    p = Parameter("UTC", start_bit=0, bit_length=24, data_type="UTC")
    assert p.decode(0x123456) == "12:34:56"


def test_arinc717_packed():
    p = Parameter("PK", start_bit=0, bit_length=5, data_type="PACKED")
    assert p.decode(0b10110) == 22


def test_arinc717_cob():
    p = Parameter(
        "MACH",
        start_bit=0,
        bit_length=16,
        data_type="COB",
        cob_formula="raw * 0.00390625",
    )
    assert abs(p.decode(256) - 1.0) < 1e-6
