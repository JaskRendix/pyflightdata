import zipfile
from pathlib import Path

import pytest

from pyarinc.io.ags import (
    AircraftRecord,
    _smart_cast,
    extract_vec_from_ags_bundle,
    find_text_vec_file,
    parse_aircraft_air,
)


@pytest.mark.parametrize(
    "protocol, bundle_name, expected_tail_fragment",
    [
        ("ags717", "010888.vec", "B-8888"),
        (
            "ags767",
            "078711.vec",
            None,
        ),  # Adjust if 767 fixture has a specific tail to assert
    ],
)
def test_ags_bundle_is_zip_and_contains_files(
    protocol, bundle_name, expected_tail_fragment
):
    fixture_dir = Path(__file__).parent / "fixtures" / protocol
    path = fixture_dir / bundle_name
    files = extract_vec_from_ags_bundle(path)

    assert isinstance(files, dict)
    assert len(files) > 0
    assert any(files.keys())


@pytest.mark.parametrize("protocol", ["ags717", "ags767"])
def test_ags_bundle_contains_no_plaintext_vec(protocol):
    fixture_dir = Path(__file__).parent / "fixtures" / protocol
    # Grab the first .vec file in the directory dynamically
    bundle_path = next(fixture_dir.glob("*.vec"))
    files = extract_vec_from_ags_bundle(bundle_path)

    for name, data in files.items():
        text = data.decode("utf-8", errors="ignore")
        assert not ("W" in text and "B" in text and "SF=" in text)


@pytest.mark.parametrize("protocol", ["ags717", "ags767"])
def test_parse_aircraft_air_utf16(protocol):
    fixture_dir = Path(__file__).parent / "fixtures" / protocol
    path = fixture_dir / "aircraft.air"
    result = parse_aircraft_air(path)

    assert result.error is None
    assert isinstance(result.records, list)
    assert len(result.records) > 0


def test_header_normalization_basic(tmp_path):
    content = "Tail\tAC TYPE\tEng1 Serial\tWeird Unicode\nB-1234\tA320\t12345\tABC\n"
    p = tmp_path / "aircraft.air"
    p.write_bytes(content.encode("utf-16-le"))

    result = parse_aircraft_air(p)
    rec = result.records[0]

    assert "tail" in rec.extra_attributes
    assert "ac_type" in rec.extra_attributes
    assert "eng1_serial" in rec.extra_attributes
    assert "weird_unicode" in rec.extra_attributes


def test_header_normalization_unicode(tmp_path):
    content = "Ｔａｉｌ\tAC TYPE\tEng1 Serial\nB-9999\tB737\t777\n"
    p = tmp_path / "aircraft_unicode.air"
    p.write_bytes(content.encode("utf-16-le"))

    result = parse_aircraft_air(p)
    rec = result.records[0]

    assert "tail" in rec.extra_attributes
    assert rec.extra_attributes["tail"] == "B-9999"


@pytest.mark.parametrize(
    "val, expected",
    [
        ("123", 123),
        ("12.5", 12.5),
        ("1e3", 1000.0),
        ("   ", ""),
        ("ABC123", "ABC123"),
    ],
)
def test_smart_cast(val, expected):
    assert _smart_cast(val) == expected


def test_record_validation():
    rec_missing_tail = AircraftRecord(tail="", ac_type="A320")
    assert "Missing aircraft tail identifier." in rec_missing_tail.validate()

    rec_missing_type = AircraftRecord(tail="B-1234", ac_type="")
    assert any("Missing aircraft type" in msg for msg in rec_missing_type.validate())


def test_truncated_row_is_padded_and_parsed(tmp_path, caplog):
    content = "Tail\tAC Type\tEng1 Serial\nB-1234\tA320\n"
    p = tmp_path / "aircraft_truncated.air"
    p.write_bytes(content.encode("utf-16-le"))

    result = parse_aircraft_air(p)
    rec = result.records[0]

    assert rec.tail == "B-1234"
    assert rec.extra_attributes["eng1_serial"] == ""
    assert "shorter than expected" in caplog.text


def test_extra_attributes_mapping(tmp_path):
    content = "Tail\tAC Type\tEng1 Serial\nB-1234\tA320\t12345\n"
    p = tmp_path / "aircraft_map.air"
    p.write_bytes(content.encode("utf-16-le"))

    result = parse_aircraft_air(p)
    rec = result.records[0]

    assert rec.extra_attributes == {
        "tail": "B-1234",
        "ac_type": "A320",
        "eng1_serial": 12345,
    }


def test_parse_aircraft_air_missing_file():
    p = Path("/nonexistent/path/aircraft.air")
    result = parse_aircraft_air(p)
    assert result.records == []
    assert result.error is not None


def test_parse_aircraft_air_invalid_utf16(tmp_path):
    p = tmp_path / "invalid.air"
    p.write_bytes(b"\x00\xFF\x00")

    result = parse_aircraft_air(p)
    assert result.records == []
    assert result.error is not None


def test_vec_heuristic_negative_binary():
    files = {"bin.dat": b"\x00\x01\x02\x03"}
    assert find_text_vec_file(files) is None


def test_vec_heuristic_positive():
    files = {"config.vec": b"TYPE=BNR\nSF=1\nW=3\nB=12"}
    name, text = find_text_vec_file(files)
    assert name == "config.vec"
    assert "TYPE=BNR" in text


def test_extract_vec_from_ags_bundle(tmp_path):
    p = tmp_path / "fake.vec"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("file1.bin", b"\x00\x01")
        zf.writestr("file2.txt", b"hello")

    files = extract_vec_from_ags_bundle(p)
    assert isinstance(files, dict)
    assert "file1.bin" in files
    assert "file2.txt" in files
    assert files["file2.txt"] == b"hello"
