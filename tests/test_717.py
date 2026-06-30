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

    assert mapping["ALT"]["word"] == 1
    assert mapping["ALT"]["bit_offset"] == 3
    assert mapping["ALT"]["length"] == 8

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

    assert params["ALT"].subframe == 0
    assert params["ALT"].word == 2
    assert params["ALT"].bit_offset == 3
    assert params["ALT"].bit_length == 8
    assert params["ALT"].rate == 4.0

    assert params["TEMP"].subframe == 1
    assert params["TEMP"].word == 5
    assert params["TEMP"].bit_offset == 0
    assert params["TEMP"].bit_length == 16
    assert params["TEMP"].rate == 1.0
    assert params["TEMP"].superframe == 2


def test_vec_717_type_token(tmp_path: Path):
    text = "ALT W1B0-7 TYPE=BNR 4.0"
    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_717(p)
    assert mapping["ALT"]["type"] == "BNR"

    params = vec_to_parameters_717(mapping)
    assert params["ALT"].data_type == "BNR"


def test_vec_717_signed_token(tmp_path: Path):
    text = "ALT W1B0-7 TYPE=BNR SIGNED=true 4.0"
    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_717(p)
    assert mapping["ALT"]["signed"] is True

    params = vec_to_parameters_717(mapping)
    assert params["ALT"].signed is True


def test_vec_717_scale_offset(tmp_path: Path):
    text = "ALT W1B0-7 TYPE=BNR SCALE=0.01 OFFSET=100 4.0"
    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_717(p)
    assert mapping["ALT"]["scale"] == 0.01
    assert mapping["ALT"]["offset"] == 100

    params = vec_to_parameters_717(mapping)
    assert params["ALT"].scale == 0.01
    assert params["ALT"].offset == 100


def test_vec_717_conv_token(tmp_path: Path):
    text = "ALT W1B0-7 TYPE=CHAR CONV=8 4.0"
    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_717(p)
    assert mapping["ALT"]["conv"] == 8

    params = vec_to_parameters_717(mapping)
    # Parameter.from_717 does NOT accept conv_config yet
    assert not hasattr(params["ALT"], "conv_config")


def test_vec_717_opt_token(tmp_path: Path):
    text = "FLAG W1B0 TYPE=DISCRETE OPT=1:ON OPT=0:OFF 1.0"
    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_717(p)
    assert mapping["FLAG"]["options"] == [(1, "ON"), (0, "OFF")]

    params = vec_to_parameters_717(mapping)
    # Parameter.from_717 does NOT accept options yet
    assert not hasattr(params["FLAG"], "options")


def test_vec_717_no_unsupported_kwargs(tmp_path: Path):
    text = "ALT W1B0-7 TYPE=BNR CONV=8 OPT=1:ON 4.0"
    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_717(p)
    params = vec_to_parameters_717(mapping)

    alt = params["ALT"]

    assert not hasattr(alt, "conv_config")
    assert not hasattr(alt, "options")


def test_vec_717_default_type(tmp_path: Path):
    text = "ALT W1B0-7 4.0"
    p = tmp_path / "test.vec"
    p.write_text(text)

    mapping = parse_vec_file_717(p)
    params = vec_to_parameters_717(mapping)

    assert params["ALT"].data_type == "DISCRETE"
