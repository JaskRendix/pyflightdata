# **pyarinc — ARINC 717 / ARINC 767 decoding library**

`pyarinc` is a modern, typed Python library for decoding ARINC 717 and ARINC 767
flight‑data recorder formats. It provides deterministic bit‑extraction utilities,
clean parameter models, PRM/VEC configuration parsing, and end‑to‑end decoding
into pandas DataFrames.

The library is designed for analysis pipelines, automated QA tooling, and
research workflows that require reliable, test‑covered decoding of FDR/QAR data.

---

## **Installation**

The package is not published on PyPI. Install locally:

### Local install
```
pip install .
```

### Editable install (recommended for development)
```
pip install -e .
```

### Install with test dependencies
```
pip install -e .[test]
```

---

## **Testing**

Run the full test suite:

```
pytest
# or
pytest -vv
```

Tests cover:

- Bit extraction (717/767, MSB‑first, cross‑byte)
- Data‑type decoding (BNR, BCD, DISCRETE, PACKED, CHAR/ASCII, UTC, COB)
- Frame reconstruction (717) and frame parsing (767)
- Scheduling and superframes
- PRM/VEC parsing
- End‑to‑end decoding for both ARINC 717 and ARINC 767

---

## **Capabilities**

### **ARINC 717**
- Detects aligned and bitstream formats  
- Converts bitstream → aligned frames  
- Reconstructs frames, subframes, and superframes  
- Decodes BNR, BCD, DISCRETE, PACKED, CHAR/ISO, UTC  
- Applies rate‑based scheduling and superframe rules  
- Produces time‑indexed parameter values  
- Word‑based parameter indexing via:
  - `subframe`
  - `word`
  - `bit_offset`
- Absolute bit indexing is *not* used for 717 parameters

### **ARINC 767**
- Frame boundary detection (sync word, header, trailer)  
- Timestamp extraction with wrap‑around handling  
- Parameter extraction using **absolute bit indexing** (`start_bit`)  
- VEC/PRM‑based configuration  
- Full data‑type support:
  - BNR (signed/unsigned)
  - BCD
  - DISCRETE
  - PACKED BITS
  - CHAR / ASCII
  - UTC
  - COB (Computed On Board) with formula evaluation  
- Scheduling:
  - Timestamp‑based time axis (primary)
  - Rate‑based scheduling (fallback, 717‑compatible)
- DataFrame output with:
  - time  
  - parameter_name  
  - value  
  - frame_index  
  - frame_id  
  - valid  

---

## **Parameter Model (717 vs 767)**

`pyarinc` uses a unified `Parameter` class with explicit separation between
ARINC 717 and ARINC 767 semantics.

### **ARINC 717 parameters**
- Use **word‑based indexing**:
  - `subframe`
  - `word`
  - `bit_offset`
- `start_bit` must remain **unset** (`None`)
- Decoded via `decode_from_frame()`
- Created using:

```python
Parameter.from_717(
    name="ALT",
    bit_length=12,
    data_type="BNR",
    subframe=0,
    word=2,
    bit_offset=4,
)
```

### **ARINC 767 parameters**
- Use **absolute bit indexing**:
  - `start_bit` (0‑based MSB‑first)
- Optional `frame_id_767` for multi‑frame configurations
- Decoded via `decode_raw_from_bytes()`
- Created using:

```python
Parameter.from_767(
    name="IAS",
    bit_length=16,
    data_type="BNR",
    start_bit=48,
    frame_id_767=3,
)
```

This separation eliminates ambiguity and prevents accidental misdecoding.

---

## **Configuration Support**

The library parses PRM and VEC formats, including:

### ARINC 717 fields
- subframe index  
- word index  
- bit offset  
- bit length  
- rate  
- superframe index  
- scale and offset  

### ARINC 767 fields
- **start_bit** (absolute bit index)  
- frame_id_767  
- bit length  
- rate  
- scale and offset  
- COB formulas  

Both JSON and text formats are supported.

---

## **Workflow**

Typical decoding flow:

1. Load raw data (aligned, bitstream, or ARINC 767 frames)  
2. Convert bitstream to aligned frames if needed (717)  
3. Load PRM or VEC configuration  
4. Construct parameters using `from_717()` or `from_767()`  
5. Decode parameters using scheduling and superframe rules  
6. Produce a pandas DataFrame  

---

## **Reference Source**

This project is a clean rewrite inspired by the decoding logic in the original
FlightDataDecode repository:

[https://github.com/osnosn/FlightDataDecode](https://github.com/osnosn/FlightDataDecode)

`pyarinc` re‑implements the core logic with a modern architecture, strict typing,
and full test coverage. No legacy scripts or `.dat` formats are included.

---

## **Notes**

- No Lua integration  
- No custom `.dat` format  
- No print() statements — uses Python logging  
- Fully typed (Python 3.12+)  
- Deterministic, testable, modular design  
