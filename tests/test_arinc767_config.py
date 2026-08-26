from pyarinc.arinc767.config import normalize_config


def test_normalize_config_identity():
    """Ensure normalize_config acts as a clean pass-through dictionary normalizer."""
    sample_config = {
        "MACH": {
            "word": 0,
            "bit_offset": 0,
            "length": 9,
            "rate": 1.0,
            "frame_id_767": 3,
            "cob_formula": "raw*0.00390625",
        }
    }

    result = normalize_config(sample_config)

    # Verify it returns the exact same structure
    assert result == sample_config
    # Verify it returns a dictionary reference
    assert isinstance(result, dict)
