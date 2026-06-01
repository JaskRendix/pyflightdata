from pathlib import Path

from pyarinc.config.vec_parser import parse_vec_file_767, vec_to_parameters_767


def test_vec_parser_767_tokens_and_hex_fid(tmp_path: Path) -> None:
    text = """
    PARAM1 W0B0-15 1.0 FID=3 COB=raw*0.00390625
    PARAM2 W1B4-15 2.0 FID=0x03 BNR
    PARAM3 W2B0-7 1.0 CHAR
    PARAM4 W3B0-11 1.0 BCD COB=raw*2
    """

    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_767(p)

    # PARAM1: decimal FID parsed, COB formula preserved
    assert "PARAM1" in mapping
    assert mapping["PARAM1"]["frame_id_767"] == 3
    assert mapping["PARAM1"]["cob_formula"] == "raw*0.00390625"
    assert mapping["PARAM1"]["word"] == 0
    assert mapping["PARAM1"]["bit_offset"] == 0
    assert mapping["PARAM1"]["length"] == 16

    # PARAM2: hex FID is NOT parsed by current implementation (expected None)
    assert "PARAM2" in mapping
    assert mapping["PARAM2"].get("frame_id_767") is None

    # Convert to Parameter objects
    params = vec_to_parameters_767(mapping)

    # Start bit calculation uses word*32 + bit_offset (current behavior)
    p1 = params["PARAM1"]
    assert p1.start_bit == 0 * 32 + 0
    assert p1.bit_length == 16
    # data_type currently defaults to DISCRETE in converter
    assert p1.data_type == "DISCRETE"
    assert p1.cob_formula == "raw*0.00390625"

    p2 = params["PARAM2"]
    assert p2.start_bit == 1 * 32 + 4
    assert p2.bit_length == 12
    # hex FID not parsed → frame_id_767 remains None on Parameter
    assert p2.frame_id_767 is None

    p3 = params["PARAM3"]
    assert p3.start_bit == 2 * 32 + 0
    assert p3.bit_length == 8

    p4 = params["PARAM4"]
    assert p4.start_bit == 3 * 32 + 0
    assert p4.bit_length == 12
    assert p4.cob_formula == "raw*2"
