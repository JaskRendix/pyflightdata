from pathlib import Path

from pyarinc.io.ags import extract_vec_from_ags_bundle, parse_aircraft_air

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "ags717"


def test_ags_bundle_is_zip_and_contains_files():
    """AGS .vec bundles are ZIP archives containing multiple files."""
    path = FIXTURE_DIR / "010888.vec"
    files = extract_vec_from_ags_bundle(path)

    assert isinstance(files, dict)
    assert len(files) > 0

    # At least one inner file must exist
    assert any(files.keys())


def test_ags_bundle_contains_no_plaintext_vec():
    """
    Real AGS .vec bundles usually contain ONLY binary/encrypted files.
    There is no plaintext VEC inside the ZIP.
    """
    path = FIXTURE_DIR / "010888.vec"
    files = extract_vec_from_ags_bundle(path)

    # Assert that none of the inner files look like a text VEC
    for name, data in files.items():
        text = data.decode("utf-8", errors="ignore")
        assert not ("W" in text and "B" in text and "SF=" in text)


def test_parse_aircraft_air_utf16():
    """Ensure aircraft.air is readable and parsed correctly."""
    path = FIXTURE_DIR / "aircraft.air"
    records = parse_aircraft_air(path)

    assert isinstance(records, list)
    assert len(records) > 0

    # Check that known tails appear
    tails = {r.tail for r in records}
    assert "B-8888" in tails
