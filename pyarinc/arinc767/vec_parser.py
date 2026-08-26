from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from ..models.parameter import Parameter

logger = logging.getLogger(__name__)

_VEC_BITRANGE_RE_767 = re.compile(
    r"W\s*(?P<word>\d+)\s*B\s*(?P<bstart>\d+)(?:-(?P<bend>\d+))?",
    re.IGNORECASE,
)


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
    """ARINC 767 VEC parser with improved hex FID and single-pass token parsing."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="latin-1").strip()
        except Exception as e:
            logger.error(f"Failed to read VEC file 767 {path}: {e}")
            raise
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
        line = line.strip()
        if not line or line.startswith("#"):
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

        # Rate extraction fallback (ignoring key-value parameters)
        for tok in reversed(parts):
            if "=" in tok:
                continue
            try:
                entry["rate"] = float(tok)
                break
            except ValueError:
                continue

        # Single-pass token processing
        for tok in parts[1:]:
            upper_tok = tok.upper()
            if upper_tok in ("BNR", "BCD", "CHAR"):
                entry["type"] = upper_tok
                continue

            if "=" not in tok:
                continue

            key, val = tok.split("=", 1)
            key = key.strip().upper()
            val = val.strip()

            if key == "FID":
                try:
                    # Support both decimal and hex (e.g. FID=0x0F)
                    base = 16 if val.lower().startswith("0x") else 10
                    entry["frame_id_767"] = int(val, base)
                except ValueError:
                    pass
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
