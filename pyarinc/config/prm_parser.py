from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models.parameter import Parameter


def parse_prm_file(path: Path) -> dict[str, Any]:
    """Parse a PRM file into a mapping of parameter definitions.

    Supported line formats (space-separated):
      name subframe word bit_offset length rate [superframe]
    Also accepts a JSON file mapping parameter names to definitions.
    """
    out: dict[str, Any] = {}
    text = path.read_text(encoding="utf-8").strip()
    # try JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        # fallback simple formats
        if len(parts) >= 6:
            try:
                name = parts[0]
                subframe = int(parts[1])
                word = int(parts[2])
                bit_offset = int(parts[3])
                length = int(parts[4])
                rate = float(parts[5])
                superframe = int(parts[6]) if len(parts) > 6 else None
            except Exception:
                continue
            out[name] = {
                "subframe": subframe,
                "word": word,
                "bit_offset": bit_offset,
                "length": length,
                "rate": rate,
                "superframe": superframe,
            }
    return out


def prm_to_parameters(mapping: dict[str, Any]) -> dict[str, Parameter]:
    """Convert a PRM mapping (from parse_prm_file) to Parameter objects."""
    from ..models.parameter import Parameter

    out: dict[str, Parameter] = {}
    for name, md in mapping.items():
        subframe = int(md.get("subframe", 0))
        word = int(md.get("word", 0))
        bit_offset = int(md.get("bit_offset", 0))
        length = int(md.get("length", 8))
        rate = float(md.get("rate", 1.0))
        superframe = md.get("superframe")
        scale = md.get("scale")
        offset = md.get("offset")
        dtype = md.get("type", "DISCRETE")

        p = Parameter.from_717(
            name=name,
            bit_length=length,
            data_type=dtype,
            subframe=subframe,
            word=word,
            bit_offset=bit_offset,
            rate=rate,
            superframe=superframe,
        )

        if scale is not None:
            p.scale = float(scale)
        if offset is not None:
            p.offset = float(offset)

        out[name] = p

    return out
