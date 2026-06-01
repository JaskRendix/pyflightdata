import pytest

from pyarinc.models.parameter import Parameter


@pytest.mark.parametrize(
    "data,start,len_bits,expected",
    [
        (b"\xCA", 0, 8, 0xCA),
        (b"\xF0\x0F", 4, 8, 0x00),
        (b"\x12\x34\x56", 8, 16, 0x3456),
    ],
)
def test_arinc767_extract_bits(data, start, len_bits, expected):
    p = Parameter("X", start_bit=start, bit_length=len_bits, data_type="DISCRETE")
    assert p.extract_bits_767(data, start, len_bits) == expected


def test_arinc767_decode_raw_from_bytes():
    data = bytes([0x12, 0x34])
    p = Parameter("ALT", start_bit=0, bit_length=16, data_type="BNR")
    assert p.decode_raw_from_bytes(data) == 0x1234


def test_arinc767_bnr_signed():
    p = Parameter("TEMP", start_bit=0, bit_length=8, data_type="BNR", signed=True)
    assert p.decode_raw_from_bytes(bytes([0xFF])) == -1


@pytest.mark.parametrize(
    "raw,expected",
    [
        (0x12, "12"),
        (0x123, "123"),
        (0x0, "0"),
    ],
)
def test_arinc767_bcd(raw, expected):
    p = Parameter("BCD", start_bit=0, bit_length=12, data_type="BCD")
    assert p.decode(raw) == expected


def test_arinc767_discrete():
    p1 = Parameter("D1", start_bit=0, bit_length=1, data_type="DISCRETE")
    assert p1.decode(1) is True
    p2 = Parameter("D2", start_bit=0, bit_length=3, data_type="DISCRETE")
    assert p2.decode(0b101) == 5


def test_arinc767_char():
    p = Parameter("CH", start_bit=0, bit_length=16, data_type="CHAR")
    assert p.decode(0x4142) == "AB"


def test_arinc767_utc():
    p = Parameter("UTC", start_bit=0, bit_length=24, data_type="UTC")
    assert p.decode(0x123456) == "12:34:56"


def test_arinc767_packed():
    p = Parameter("PK", start_bit=0, bit_length=5, data_type="PACKED")
    assert p.decode(0b10110) == 22


def test_arinc767_cob():
    p = Parameter(
        "MACH",
        start_bit=0,
        bit_length=16,
        data_type="COB",
        cob_formula="raw * 0.00390625",
    )
    assert abs(p.decode(256) - 1.0) < 1e-6


def test_arinc767_decode_out_of_bounds():
    p = Parameter("X", start_bit=32, bit_length=8, data_type="BNR")
    with pytest.raises(Exception):
        _ = p.decode_raw_from_bytes(b"\x00\x00\x00\x00")
