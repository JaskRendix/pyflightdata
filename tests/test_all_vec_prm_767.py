from __future__ import annotations

from pathlib import Path

from pyarinc.arinc767.decoder import Arinc767Decoder
from pyarinc.arinc767.frame import Arinc767Frame, Arinc767FrameParser
from pyarinc.config.prm_parser import parse_prm_file, prm_to_parameters
from pyarinc.config.vec_parser import parse_vec_file as parse_vec_file_717
from pyarinc.config.vec_parser import parse_vec_file_767
from pyarinc.config.vec_parser import vec_to_parameters as vec_to_parameters_717
from pyarinc.config.vec_parser import vec_to_parameters_767
from pyarinc.models.parameter import Parameter


def test_vec_bitrange_parsing_717(tmp_path: Path):
    text = """
    ALT W2B3-10  BNR  4.0
    SPD W3B1-8  BCD 8.0 SF=1
    """
    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_717(p)

    # ALT
    assert "ALT" in mapping
    assert mapping["ALT"]["word"] == 1  # W2 → index 1
    assert mapping["ALT"]["bit_offset"] == 3
    assert mapping["ALT"]["length"] == 8

    # SPD
    assert "SPD" in mapping
    assert mapping["SPD"]["word"] == 2
    assert mapping["SPD"]["bit_offset"] == 1
    assert mapping["SPD"]["length"] == 8
    assert mapping["SPD"]["superframe"] == 1

    params = vec_to_parameters_717(mapping)
    assert params["ALT"].word == 1
    assert params["ALT"].bit_offset == 3
    assert params["ALT"].bit_length == 8
    assert params["ALT"].rate == 4.0


def test_prm_line_parsing_717(tmp_path: Path):
    text = """
    ALT 0 2 3 8 4.0
    TEMP 1 5 0 16 1.0 2
    """
    p = tmp_path / "test.prm"
    p.write_text(text)

    mapping = parse_prm_file(p)
    params = prm_to_parameters(mapping)

    # ALT
    assert params["ALT"].subframe == 0
    assert params["ALT"].word == 2
    assert params["ALT"].bit_offset == 3
    assert params["ALT"].bit_length == 8
    assert params["ALT"].rate == 4.0

    # TEMP
    assert params["TEMP"].subframe == 1
    assert params["TEMP"].word == 5
    assert params["TEMP"].bit_offset == 0
    assert params["TEMP"].bit_length == 16
    assert params["TEMP"].rate == 1.0
    assert params["TEMP"].superframe == 2


def test_vec_767_parsing(tmp_path: Path):
    text = "MACH W0B0-8 1.0 FID=3 COB=raw*0.00390625"
    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_767(p)
    assert "MACH" in mapping

    m = mapping["MACH"]
    assert m["word"] == 0
    assert m["bit_offset"] == 0
    assert m["length"] == 9
    assert m["rate"] == 1.0
    assert m["frame_id_767"] == 3
    assert m["cob_formula"] == "raw*0.00390625"

    params = vec_to_parameters_767(mapping)
    p_mach = params["MACH"]

    assert p_mach.start_bit == 0
    assert p_mach.bit_length == 9
    assert p_mach.frame_id_767 == 3
    assert p_mach.cob_formula == "raw*0.00390625"


def test_extract_bits_767_cross_boundary():
    data = bytes([0b11110000, 0b00001111])  # 0xF0, 0x0F
    p = Parameter(name="X", start_bit=4, bit_length=8, data_type="DISCRETE")
    raw = p.extract_bits_767(data, 4, 8)
    assert raw == 0b00000000  # top 4 bits of 0xF0 + bottom 4 bits of 0x0F


def test_decode_bnr_767():
    p = Parameter(
        name="ALT",
        start_bit=0,
        bit_length=16,
        data_type="BNR",
        scale=1.0,
        offset=0.0,
        signed=False,
    )
    data = bytes([0x12, 0x34])
    assert p.decode_raw_from_bytes(data) == 0x1234


def test_decode_cob_767():
    p = Parameter(
        name="MACH",
        start_bit=0,
        bit_length=16,
        data_type="COB",
        cob_formula="raw * 0.00390625",
    )
    data = bytes([0x01, 0x00])  # raw = 256
    assert abs(p.decode_raw_from_bytes(data) - 1.0) < 1e-6


def test_arinc767_frame_parsing_basic():
    # sync EB90, length 14, timestamp 1, type=0, id=3, data=ABCD, trailer=0003
    raw = bytes.fromhex("EB90" "000E" "00000001" "00" "03" "ABCD" "0003")

    frames = list(Arinc767FrameParser.iter_frames(raw))
    assert len(frames) == 1

    f = frames[0]
    assert f.frame_id == 3
    assert f.frame_type == 0
    assert f.timestamp_ms == 1
    assert f.data == bytes.fromhex("ABCD")


def test_arinc767_decoder_basic():
    raw = bytes.fromhex("EB90" "000E" "00000000" "00" "01" "1234" "0001")

    frame = Arinc767Frame(
        raw_bytes=raw,
        frame_index=0,
        frame_id=1,
        frame_type=0,
        timestamp_ms=0,
    )

    p = Parameter(
        name="X",
        start_bit=0,
        bit_length=16,
        data_type="DISCRETE",
        frame_id_767=1,
    )

    dec = Arinc767Decoder([p])
    df = dec.decode_frames([frame])

    assert df.loc[0, "X"] == 0x1234
    assert df.loc[0, "X_valid"] == True


def test_arinc767_decoder_scheduled():
    raw = bytes.fromhex("EB90" "000E" "00000000" "00" "01" "1234" "0001")
    frame0 = Arinc767Frame(raw, 0, 1, 0, 0)
    frame1 = Arinc767Frame(raw, 1, 1, 0, 0)

    p = Parameter(
        name="X",
        start_bit=0,
        bit_length=16,
        data_type="DISCRETE",
        frame_id_767=1,
        rate=0.5,  # sample every 2 frames
    )

    dec = Arinc767Decoder([p], frames_per_second=1.0)
    df = dec.decode([frame0, frame1])

    assert df.iloc[0]["valid"] == True
    assert df.iloc[1]["valid"] == False
