from __future__ import annotations

from pyarinc.arinc717.config import normalize_config


def test_arinc717_normalize_config_identity():
    """Ensure ARINC 717 normalize_config acts as a clean pass-through dictionary normalizer."""
    sample_config = {
        "ALTITUDE": {
            "subframe": 1,
            "word": 12,
            "bit_offset": 0,
            "length": 12,
            "rate": 1.0,
            "data_type": "BNR",
        }
    }

    result = normalize_config(sample_config)

    # Verify it returns the exact same structure
    assert result == sample_config
    # Verify it returns a dictionary reference
    assert isinstance(result, dict)
