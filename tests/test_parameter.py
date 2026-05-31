from pyarinc.models.parameter import Parameter


def test_parameter_bnr_unsigned_and_signed():
    # unsigned BNR
    p = Parameter(name="ALT", start_bit=0, bit_length=16, data_type="BNR", scale=0.5)
    assert p.decode(100) == 50.0
    # signed BNR: -1 represented in 8 bits is 0xFF
    ps = Parameter(name="TEMP", start_bit=0, bit_length=8, data_type="BNR", signed=True)
    assert ps.decode(0xFF) == -1.0


def test_parameter_bcd_and_char_and_discrete_and_utc():
    p = Parameter(name="BCD", start_bit=0, bit_length=8, data_type="BCD")
    assert p.decode(0x12) == "12"
    p2 = Parameter(name="CH", start_bit=0, bit_length=16, data_type="CHAR")
    # 'A' = 0x41, 'B' = 0x42 -> packed would be 0x4142
    assert p2.decode(0x4142) == "AB"
    d1 = Parameter(name="D1", start_bit=0, bit_length=1, data_type="DISCRETE")
    assert d1.decode(1) is True
    d2 = Parameter(name="D2", start_bit=0, bit_length=3, data_type="DISCRETE")
    assert d2.decode(0b101) == 5
    # UTC as packed BCD HHMMSS -> 12:34:56 is 0x123456
    utc = Parameter(name="T", start_bit=0, bit_length=24, data_type="UTC")
    assert utc.decode(0x123456) == "12:34:56"
