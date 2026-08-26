from __future__ import annotations

import json
import logging
import re
import zipfile
from pathlib import Path
from typing import Any

from ..models.parameter import Parameter

logger = logging.getLogger(__name__)

_VEC_BITRANGE_RE_767 = re.compile(
    r"W\s*(?P<word>\d+)\s*B\s*(?P<bstart>\d+)(?:-(?P<bend>\d+))?",
    re.IGNORECASE,
)


def _read_text_file(path: Path) -> str:
    """Read text file, safely handling ZIP archives, UTF-16 BOMs, and standard encodings."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, "r") as z:
            namelist = z.namelist()
            par_files = [f for f in namelist if f.endswith(".par")]
            target_file = par_files[0] if par_files else namelist[0]
            raw_bytes = z.read(target_file)
    else:
        raw_bytes = path.read_bytes()

    # Check if bytes actually have a UTF-16 BOM (FF FE or FE FF) or start with null bytes characteristic of UTF-16 text
    encodings = ("utf-8", "latin-1", "cp1252")
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings = ("utf-16",) + encodings

    for encoding in encodings:
        try:
            return raw_bytes.decode(encoding).strip()
        except UnicodeDecodeError:
            continue

    # Absolute fallback
    return raw_bytes.decode("utf-8", errors="ignore").strip()


def _parse_bitrange_767(token: str) -> dict[str, int] | None:
    m = _VEC_BITRANGE_RE_767.search(token)
    if not m:
        return None

    word = int(m.group("word"))
    bstart = int(m.group("bstart"))
    bend = m.group("bend")
    bend_i = int(bend) if bend is not None else bstart
    length = bend_i - bstart + 1

    return {
        "word": word,
        "bit_offset": bstart,
        "length": length,
    }


def parse_vec_file_767(path: Path) -> dict[str, Any]:
    """Advanced ARINC 767 VEC parser with robust encoding, inline comment stripping, and validation."""
    try:
        text = _read_text_file(path)
    except Exception as e:
        logger.error(f"Failed to read VEC file 767 {path}: {e}")
        raise

    # JSON shortcut
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    out: dict[str, Any] = {}

    for line_num, line in enumerate(text.splitlines(), start=1):
        # Strip inline comments and whitespace
        line = line.split("#")[0].strip()
        if not line:
            continue

        parts = line.split()
        if not parts:
            continue

        name = parts[0]
        entry: dict[str, Any] = {
            "frame_id_767": None,
            "cob_formula": None,
            "rate": 1.0,
        }

        # Bitrange extraction
        for tok in parts[1:]:
            br = _parse_bitrange_767(tok)
            if br:
                entry.update(br)
                break

        if "word" not in entry:
            logger.debug(f"Line {line_num}: No bitrange found for parameter '{name}'")

        # Rate extraction fallback (ignoring key-value parameters)
        for tok in reversed(parts):
            if "=" in tok:
                continue
            try:
                entry["rate"] = float(tok)
                break
            except ValueError:
                continue

        # Single-pass token processing for metadata flags
        for tok in parts[1:]:
            upper_tok = tok.upper()
            if upper_tok in ("BNR", "BCD", "CHAR", "DISCRETE"):
                entry["type"] = upper_tok
                continue

            if "=" not in tok:
                continue

            key, val = tok.split("=", 1)
            key = key.strip().upper()
            val = val.strip()

            if key == "FID":
                try:
                    base = 16 if val.lower().startswith("0x") else 10
                    entry["frame_id_767"] = int(val, base)
                except ValueError:
                    logger.warning(
                        f"Line {line_num}: Invalid FID value '{val}' for parameter '{name}'"
                    )
            elif key == "COB":
                entry["cob_formula"] = val
            elif key == "TYPE":
                entry["type"] = val.upper()
            elif key == "SCALE":
                try:
                    entry["scale"] = float(val)
                except ValueError:
                    pass
            elif key == "OFFSET":
                try:
                    entry["offset"] = float(val)
                except ValueError:
                    pass
            elif key == "SIGNED":
                entry["signed"] = val.lower() == "true"

        out[name] = entry

    return out


def vec_to_parameters_767(
    mapping: dict[str, Any],
    default_rate: float = 1.0,
) -> dict[str, Parameter]:
    """Convert ARINC 767 VEC mapping to Parameter objects."""
    out: dict[str, Parameter] = {}

    for name, md in mapping.items():
        word = int(md.get("word", 0))
        bit_offset = int(md.get("bit_offset", 0))
        length = int(md.get("length", 1))
        rate = float(md.get("rate", default_rate))

        frame_id_767 = md.get("frame_id_767")
        cob_formula = md.get("cob_formula")
        dtype = md.get("type", "DISCRETE").upper()
        scale = md.get("scale")
        offset = md.get("offset")
        signed = md.get("signed", False)

        start_bit = word * 32 + bit_offset

        p = Parameter.from_767(
            name=name,
            bit_length=length,
            data_type=dtype,
            start_bit=start_bit,
            frame_id_767=frame_id_767,
            rate=rate,
            cob_formula=cob_formula,
            scale=scale,
            offset=offset,
            signed=signed,
        )

        out[name] = p

    return out
