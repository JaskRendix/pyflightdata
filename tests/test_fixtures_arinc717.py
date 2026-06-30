from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ags717"


def test_fixture_files_exist():
    assert (FIXTURE_DIR / "010888.vec").exists()
    assert (FIXTURE_DIR / "aircraft.air").exists()
    assert (FIXTURE_DIR / "README.md").exists()


def test_010888_vec_is_zip():
    data = (FIXTURE_DIR / "010888.vec").read_bytes()
    assert data.startswith(b"PK\x03\x04")


def test_aircraft_air_is_utf16():
    data = (FIXTURE_DIR / "aircraft.air").read_bytes()
    assert data.startswith(b"\xff\xfe")
