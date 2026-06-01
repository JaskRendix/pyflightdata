# pyarinc — ARINC 717 / ARINC 767 decoding library

`pyarinc` is a modern, typed Python library for decoding ARINC 717 and ARINC 767
flight‑data recorder formats. It provides a clean architecture, deterministic
bit‑extraction utilities, configuration parsing (PRM/VEC), and end‑to‑end
decoding into pandas DataFrames.

The library is designed for analysis pipelines, automated QA tooling, and
research workflows that require reliable, test‑covered decoding of FDR/QAR data.

---

## Installation

The package is not published on PyPI. Install locally:

### Local install
pip install .

### Editable install (recommended for development)
pip install -e .

### Install with test dependencies
pip install -e .[test]

---

## Testing

Run the full test suite:

pytest
# or
pytest -vv

Tests cover:

- Bit extraction (717/767, MSB‑first, cross‑byte)
- Data‑type decoding (BNR, BCD, DISCRETE, PACKED, CHAR/ASCII, UTC, COB)
- Frame reconstruction (717) and frame parsing (767)
- Scheduling and superframes
- PRM/VEC parsing
- End‑to‑end decoding for both ARINC 717 and ARINC 767

---

## Capabilities

### ARINC 717
- Detects aligned and bitstream formats
- Converts bitstream → aligned frames
- Reconstructs frames, subframes, and superframes
- Decodes BNR, BCD, DISCRETE, PACKED, CHAR/ISO, UTC
- Applies rate‑based scheduling and superframe rules
- Produces time‑indexed parameter values

### ARINC 767
- Frame boundary detection (sync word, header, trailer)
- Timestamp extraction
- Parameter extraction using absolute bit indexing
- VEC/PRM‑based configuration (word, bit offset, length, rate)
- Full data‑type support:
  - BNR (signed/unsigned)
  - BCD
  - DISCRETE
  - PACKED BITS
  - CHAR / ASCII
  - UTC
  - COB (Computed On Board) with formula evaluation
- Rate‑based scheduling (same semantics as ARINC 717)
- DataFrame output with time, parameter_name, value, frame_index, frame_id, valid

---

## Configuration Support

The library parses PRM and VEC formats, including:

- subframe index (717)
- word index and bit offset
- bit length
- rate
- superframe index (717)
- scale and offset
- ARINC 767 fields:
  - frame_id_767
  - COB formulas

JSON and text formats are supported.

---

## Workflow

Typical decoding flow:

1. Load raw data (aligned, bitstream, or ARINC 767 frames)
2. Convert bitstream to aligned frames if needed (717)
3. Load PRM or VEC configuration
4. Decode parameters using scheduling and superframe rules
5. Produce a pandas DataFrame

---

## Reference Source

This project is a clean rewrite inspired by the decoding logic in the original
FlightDataDecode repository:

https://github.com/osnosn/FlightDataDecode

`pyarinc` re‑implements the core logic with a modern architecture, strict typing,
and full test coverage. No legacy scripts or `.dat` formats are included.

---

## Notes

- No Lua integration
- No custom `.dat` format
- No print() statements — uses Python logging
- Fully typed (Python 3.12+)
- Deterministic, testable, modular design
