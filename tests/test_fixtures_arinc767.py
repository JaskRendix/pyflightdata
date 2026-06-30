from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ags767"


def test_fixture_files_exist():
    assert (FIXTURE_DIR / "078711.vec").exists()
    assert (FIXTURE_DIR / "aircraft.air").exists()


def test_078711_vec_is_zip():
    data = (FIXTURE_DIR / "078711.vec").read_bytes()
    assert data.startswith(b"PK\x03\x04")  # ZIP magic


def test_aircraft_air_is_utf16():
    data = (FIXTURE_DIR / "aircraft.air").read_bytes()
    assert data.startswith(b"\xff\xfe")  # UTF‑16LE BOM
