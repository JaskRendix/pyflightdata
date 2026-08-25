# **pyarinc — ARINC 717 / ARINC 767 decoding library**

`pyarinc` is a modern, typed Python library for decoding ARINC 717 and ARINC 767 flight‑data recorder formats.  
It provides deterministic bit‑extraction utilities, clean parameter models, PRM/VEC configuration parsing, ARINC 647A (FRED) XML support, and end‑to‑end decoding into pandas DataFrames.

The library is designed for analysis pipelines, automated QA tooling, and research workflows that require reliable, test‑covered decoding of FDR/QAR data.

---

## **Installation**

### **Standard installation**
```
pip install .
```

### **Editable installation (recommended for development)**
```
pip install -e .
```

### **Install optional extras**

#### **I/O support (Parquet, Arrow)**
```
pip install -e .[io]
```

#### **Development tools (pytest, coverage, Arrow)**
```
pip install -e .[dev]
```

#### **Test dependencies only**
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
- PRM/VEC and ARINC 647A FRED XML parsing  
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
- Raw‑byte convenience decoding via `decode_raw_bytes()`  
- Word‑based parameter indexing:
  - `subframe`
  - `word`
  - `bit_offset`  
- Absolute bit indexing is **not** used for 717 parameters  

### **ARINC 767**
- Frame boundary detection (sync word, header, trailer)  
- Timestamp extraction with wrap‑around handling  
- Parameter extraction using **absolute bit indexing** (`start_bit`)  
- VEC/PRM/FRED‑based configuration  
- Raw‑byte convenience decoding via `decode_raw_bytes()`  
- Full data‑type support:
  - BNR (signed/unsigned)
  - BCD
  - DISCRETE
  - PACKED BITS
  - CHAR / ASCII
  - UTC
  - COB (Computed On Board)  
- Scheduling:
  - Timestamp‑based time axis (primary)
  - Rate‑based scheduling (fallback, 717‑compatible)  
- DataFrame output with:
  - `time`
  - `parameter_name`
  - `value`
  - `frame_index`
  - `frame_id`
  - `valid`

---

## **Parameter Model (717 vs 767)**

`pyarinc` uses a unified `Parameter` class with explicit separation between ARINC 717 and ARINC 767 semantics.

### **ARINC 717 parameters**
- Word‑based indexing:
  - `subframe`
  - `word`
  - `bit_offset`
- `start_bit` must remain **unset** (`None`)  
- Decoded via `decode_from_frame()`  

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

* Absolute bit indexing (`start_bit`)
* Optional `frame_id_767` for multi‑frame configurations
* Decoded via `decode_raw_from_bytes()`

```python
Parameter.from_767(
    name="IAS",
    bit_length=16,
    data_type="BNR",
    start_bit=48,
    frame_id_767=3,
)
```

---

## **Configuration Support**

### **ARINC 717 fields**

* subframe index
* word index
* bit offset
* bit length
* rate
* superframe index
* scale and offset

### **ARINC 767 fields**

* `start_bit`
* `frame_id_767`
* bit length
* rate
* scale and offset
* COB formulas

### **ARINC 647A FRED XML Support**

* Schema-agnostic element discovery for Flight Recorder Electronic Documentation
* Parent-child metadata fallback and subparameter unit inheritance
* Strict, warning, and lenient validation modes (`StrictMode`) via `FredXmlParser`
* Automated extraction and mapping into core library parameter models

Both JSON, text, VEC/PRM, and FRED XML formats are supported.

---

## **VEC Parsing Enhancements**

### **ARINC 717**

* `TYPE=`, `SIGNED=`, `SCALE=`, `OFFSET=`
* Bare type tokens (`BNR`, `BCD`, `CHAR`)
* `CONV=` and `OPT=` tokens retained for future use

### **ARINC 767**

* Bare type tokens
* `SIGNED=`, `SCALE=`, `OFFSET=`
* Decimal `FID=` supported
* COB formulas stored without overriding declared type
* Absolute bit indexing preserved

### **General**

* Unified token handling across 717/767
* Expanded test coverage
* No changes to the public `Parameter` API

---

## **Workflow**

1. Load raw data (aligned, bitstream, or ARINC 767 frames)
2. Convert bitstream → aligned frames if needed (717)
3. Load PRM, VEC, or ARINC 647A FRED XML configurations
4. Construct parameters using `from_717()` or `from_767()`
5. Decode using scheduling and superframe rules
6. Export DataFrame to CSV or Parquet

Reference examples:

* `examples/process_flight.py` (ARINC 717)
* `examples/process_flight_767.py` (ARINC 767)
* `examples/parse_fred_example.py` (ARINC 647A FRED XML Parsing)

---

## **Reference Source**

This project is a clean rewrite inspired by:

[https://github.com/osnosn/FlightDataDecode](https://github.com/osnosn/FlightDataDecode)

`pyarinc` re‑implements the core logic with a modern architecture, strict typing, and full test coverage.

---

## **Notes**

* No Lua integration
* No legacy `.dat` formats
* No `print()` statements — uses Python logging
* Fully typed (Python 3.12+)
* Deterministic, testable, modular design
