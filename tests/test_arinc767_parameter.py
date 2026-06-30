import pytest

from pyarinc.models.parameter import Parameter


@pytest.mark.parametrize(
    "data,start,len_bits,expected",
    [
        (b"\xCA", 0, 8, 0xCA),
        (b"\xF0\x0F", 4, 8, 0x00),
        (b"\x12\x34\x56", 8, 16, 0x3456),
        (b"\x12\x34\x56", 0, 8, 0x12),
        (b"\xFF\x01", 7, 9, 257),
    ],
)
def test_arinc767_extract_bits(
    data: bytes, start: int, len_bits: int, expected: int
) -> None:
    p = Parameter("X", start_bit=start, bit_length=len_bits, data_type="DISCRETE")
    assert p.extract_bits_767(data, start, len_bits) == expected


def test_arinc767_decode_raw_from_bytes() -> None:
    data = bytes([0x12, 0x34])
    p = Parameter("ALT", start_bit=0, bit_length=16, data_type="BNR")
    assert p.decode_raw_from_bytes(data) == 0x1234


@pytest.mark.parametrize(
    "val_bytes,bit_length,signed,expected",
    [
        (b"\xFF", 8, True, -1),
        (b"\x80", 8, True, -128),
        (b"\x7F", 8, True, 127),
        (b"\xFF\xFF", 16, False, 0xFFFF),
        (b"\xFF\xFF", 16, True, -1),
    ],
)
def test_arinc767_bnr_signed_unsigned(
    val_bytes: bytes, bit_length: int, signed: bool, expected: int
) -> None:
    p = Parameter(
        "TEMP", start_bit=0, bit_length=bit_length, data_type="BNR", signed=signed
    )
    assert p.decode_raw_from_bytes(val_bytes) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (0x12, "12"),
        (0x123, "123"),
        (0x0, "0"),
    ],
)
def test_arinc767_bcd(raw: int, expected: str) -> None:
    p = Parameter("BCD", start_bit=0, bit_length=12, data_type="BCD")
    assert p.decode(raw) == expected


def test_arinc767_discrete() -> None:
    p1 = Parameter("D1", start_bit=0, bit_length=1, data_type="DISCRETE")
    assert p1.decode(1) is True
    p2 = Parameter("D2", start_bit=0, bit_length=3, data_type="DISCRETE")
    assert p2.decode(0b101) == 5


def test_arinc767_char_multi_byte() -> None:
    # 3-byte ASCII "ABC"
    raw = int.from_bytes(b"ABC", "big")
    p = Parameter("CH3", start_bit=0, bit_length=24, data_type="CHAR")
    assert p.decode(raw) == "ABC"


def test_arinc767_utc_and_packed() -> None:
    p_utc = Parameter("UTC", start_bit=0, bit_length=24, data_type="UTC")
    assert p_utc.decode(0x123456) == "12:34:56"

    p_pk = Parameter("PK", start_bit=0, bit_length=5, data_type="PACKED")
    assert p_pk.decode(0b10110) == 22


def test_arinc767_cob_formula_scale_offset() -> None:
    p = Parameter(
        "VAL",
        start_bit=0,
        bit_length=16,
        data_type="COB",
        cob_formula="raw * scale + offset",
        scale=0.5,
        offset=1.0,
    )
    assert p.decode(100) == pytest.approx(51.0)


def test_arinc767_extract_out_of_bounds_raises() -> None:
    p = Parameter("X", start_bit=32, bit_length=8, data_type="BNR")
    with pytest.raises(ValueError):
        _ = p.decode_raw_from_bytes(b"\x00\x00\x00\x00")


def test_signed_cross_byte_extraction():
    # 0b0111_1111_1111_1111 = +32767
    # 0b1000_0000_0000_0001 = -32767 (two's complement)
    data_pos = b"\x7F\xFF"
    data_neg = b"\x80\x01"

    p = Parameter("X", start_bit=0, bit_length=16, data_type="BNR", signed=True)

    assert p.decode_raw_from_bytes(data_pos) == 32767
    assert p.decode_raw_from_bytes(data_neg) == -32767


def test_char_with_embedded_nulls():
    raw = int.from_bytes(b"A\x00C", "big")
    p = Parameter("CH", start_bit=0, bit_length=24, data_type="CHAR")
    assert p.decode(raw) == "A\x00C"


def test_utc_leading_zero():
    p = Parameter("UTC", start_bit=0, bit_length=24, data_type="UTC")
    assert p.decode(0x012305) == "01:23:05"


def test_cob_formula_failure_falls_back_to_raw():
    p = Parameter(
        "BAD",
        start_bit=0,
        bit_length=8,
        data_type="COB",
        cob_formula="raw / 0",  # division by zero
    )
    assert p.decode(10) == 10


def test_767_decode_raw_requires_start_bit():
    p = Parameter("X", bit_length=8, data_type="BNR", start_bit=None)
    with pytest.raises(ValueError):
        p.decode_raw_from_bytes(b"\x00")


def test_767_extract_non_byte_aligned():
    data = b"\xAA\xBB\xCC"  # 10101010 10111011 11001100
    p = Parameter("X", start_bit=5, bit_length=10, data_type="DISCRETE")
    assert p.extract_bits_767(data, 5, 10) == 0b0101011101


def test_767_partial_data_rejected():
    p = Parameter("X", start_bit=8, bit_length=16, data_type="BNR")
    with pytest.raises(ValueError):
        p.decode_raw_from_bytes(b"\x12")  # only 8 bits available
