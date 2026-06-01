from pathlib import Path

from pyarinc.config.prm_parser import parse_prm_file, prm_to_parameters


def test_prm_line_parsing(tmp_path: Path):
    text = """
    ALT 0 2 3 8 4.0
    TEMP 1 5 0 16 1.0 2
    """
    p = tmp_path / "test.prm"
    p.write_text(text)

    mapping = parse_prm_file(p)

    assert "ALT" in mapping
    assert "TEMP" in mapping

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
