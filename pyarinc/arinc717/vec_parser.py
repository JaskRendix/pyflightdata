from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from ..models.parameter import Parameter

logger = logging.getLogger(__name__)

_VEC_BITRANGE_RE_717 = re.compile(
    r"W\s*(?P<word>\d+)\s*B\s*(?P<bstart>\d+)(?:-(?P<bend>\d+))?",
    re.IGNORECASE,
)


def _parse_bitrange_717(token: str) -> dict[str, int] | None:
    m = _VEC_BITRANGE_RE_717.search(token)
    if not m:
        return None
    word = int(m.group("word"))
    bstart = int(m.group("bstart"))
    bend = m.group("bend")
    bend_i = int(bend) if bend is not None else bstart
    length = bend_i - bstart + 1
    return {
        "word": word - 1,  # 717 uses 12-bit aligned words -> 0-based
        "bit_offset": bstart,
        "length": length,
    }


def parse_vec_file_717(path: Path) -> dict[str, Any]:
    """ARINC 717 VEC parser with single-pass token scanning."""
    out: dict[str, Any] = {}
    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.error(f"Failed to read VEC file 717 {path}: {e}")
        raise

    # JSON shortcut
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    for line_num, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if not parts:
            continue

        name = parts[0]
        entry: dict[str, Any] = {"subframe": 0}
        options = []

        # Bitrange extraction (typically found early in parts)
        for tok in parts[1:6]:
            br = _parse_bitrange_717(tok)
            if br:
                entry.update(br)
                break

        # Rate extraction (fallback to scanning for float tokens safely)
        for tok in reversed(parts):
            if "=" in tok:
                continue
            try:
                entry["rate"] = float(tok)
                break
            except ValueError:
                continue
        entry.setdefault("rate", 1.0)

        # Single-pass keyword and token parsing
        for tok in parts[1:]:
            upper_tok = tok.upper()

            # Bare type tokens
            if upper_tok in ("BNR", "BCD", "CHAR"):
                entry["type"] = upper_tok
                continue

            if "=" not in tok:
                continue

            key, val = tok.split("=", 1)
            key = key.strip().upper()
            val = val.strip()

            if key == "SF":
                try:
                    entry["superframe"] = int(val)
                except ValueError:
                    pass
            elif key == "TYPE":
                entry["type"] = val.upper()
            elif key == "SIGNED":
                entry["signed"] = val.lower() == "true"
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
            elif key == "CONV":
                try:
                    entry["conv"] = int(val)
                except ValueError:
                    pass
            elif key == "OPT":
                try:
                    opt_val, txt = val.split(":", 1)
                    options.append((int(opt_val), txt))
                except Exception:
                    pass

        if options:
            entry["options"] = options

        out[name] = entry

    return out


def vec_to_parameters_717(
    mapping: dict[str, Any],
    default_rate: float = 1.0,
) -> dict[str, Parameter]:
    """Convert ARINC 717 VEC mapping to Parameter objects."""
    out: dict[str, Parameter] = {}

    for name, md in mapping.items():
        subframe = int(md.get("subframe", 0))
        word = int(md.get("word", 0))
        bit_offset = int(md.get("bit_offset", 0))
        length = int(md.get("length", 8))
        rate = float(md.get("rate", default_rate))
        superframe = md.get("superframe")

        dtype = md.get("type", "DISCRETE").upper()
        scale = md.get("scale")
        offset = md.get("offset")
        signed = md.get("signed", False)

        p = Parameter.from_717(
            name=name,
            bit_length=length,
            data_type=dtype,
            subframe=subframe,
            word=word,
            bit_offset=bit_offset,
            rate=rate,
            superframe=superframe,
            signed=signed,
            scale=scale,
            offset=offset,
        )

        out[name] = p

    return out
