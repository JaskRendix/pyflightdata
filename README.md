# **pyarinc — ARINC 717 / 767 decoding library**

`pyarinc` is a modern Python library for decoding ARINC 717 and ARINC 767 flight‑data recorder formats.  
The codebase is typed, modular, and designed for integration into analysis pipelines.  
See the `pyarinc` package for modules and `tests/` for usage examples.

---

# **Installation**

The package is not published on PyPI. Install it locally:

### **Local install**
```
pip install .
```

### **Editable install (recommended for development)**
```
pip install -e .
```

### **Install with test dependencies**
```
pip install -e .[test]
```

---

# **Testing**

Run the full test suite:

```
pytest
```

or with verbose output:

```
pytest -vv
```

Tests cover:

- bit extraction  
- data‑type decoding  
- frame reconstruction  
- scheduling and superframes  
- PRM/VEC parsing  
- end‑to‑end ARINC 717 decoding  

---

# **Reference Source**

This project is a clean rewrite inspired by the decoding logic in the original repository:  
**[https://github.com/osnosn/FlightDataDecode](https://github.com/osnosn/FlightDataDecode)**

The original repo contains exploratory scripts and documentation for ARINC 717 and ARINC 767 decoding.  
`pyarinc` re‑implements the core logic with a modern architecture and test coverage.

---

# **Capabilities**

### **ARINC 717**
- Detects aligned and bitstream formats  
- Converts bitstream → aligned frames  
- Reconstructs frames, subframes, and superframes  
- Decodes BNR, BCD, DISCRETE, PACKED BITS, CHAR/ISO, UTC  
- Applies rate‑based scheduling and superframe rules  
- Produces time‑indexed parameter values  

### **ARINC 767**
- Frame boundary detection  
- Parameter extraction using VEC/PRM definitions  
- Support for “COMPUTED ON BOARD” parameter types  

---

# **Configuration Support**

The library parses PRM and VEC formats, including:

- subframe index  
- word index  
- bit offset and length  
- rate  
- superframe index  
- scale and offset  

JSON and text formats are supported.

---

# **Workflow**

Typical decoding flow:

1. Load raw data (aligned or bitstream).  
2. Convert bitstream to aligned frames if needed.  
3. Load PRM or VEC configuration.  
4. Decode parameters using scheduling and superframe rules.  
5. Produce a pandas DataFrame.

---

# **Notes**

This library does not include the custom `.dat` format or Lua‑based post‑processing from the original repo.  
It focuses on decoding logic and structured output.
