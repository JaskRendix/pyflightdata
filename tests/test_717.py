from __future__ import annotations

from pathlib import Path

from pyarinc.config.prm_parser import parse_prm_file, prm_to_parameters
from pyarinc.config.vec_parser import parse_vec_file as parse_vec_file_717
from pyarinc.config.vec_parser import vec_to_parameters as vec_to_parameters_717


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
