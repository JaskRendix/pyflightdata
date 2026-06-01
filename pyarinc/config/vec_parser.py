from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..models.parameter import Parameter

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
    bit_offset = bstart
    length = bend_i - bstart + 1
    return {"word": word - 1, "bit_offset": bit_offset, "length": length}


def parse_vec_file_717(path: Path) -> dict[str, Any]:
    """Legacy ARINC 717 VEC parser."""
    out: dict[str, Any] = {}
    text = path.read_text(encoding="utf-8").strip()

    # JSON shortcut
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
        name = parts[0]
        entry: dict[str, Any] = {}

        # bitrange
        for tok in parts[1:6]:
            br = _parse_bitrange_717(tok)
            if br:
                entry.update(br)
                break

        # rate
        for tok in reversed(parts):
            try:
                entry["rate"] = float(tok)
                break
            except Exception:
                continue

        # superframe
        sf = None
        for tok in parts:
            if tok.upper().startswith("SF="):
                try:
                    sf = int(tok.split("=")[1])
                except Exception:
                    pass
        if sf is not None:
            entry["superframe"] = sf

        entry.setdefault("subframe", 0)
        out[name] = entry

    return out


def vec_to_parameters_717(
    mapping: dict[str, Any], default_rate: float = 1.0
) -> dict[str, Parameter]:
    """Legacy ARINC 717 converter."""
    out: dict[str, Parameter] = {}

    for name, md in mapping.items():
        subframe = int(md.get("subframe", 0))
        word = int(md.get("word", 0))
        bit_offset = int(md.get("bit_offset", 0))
        length = int(md.get("length", 8))
        rate = float(md.get("rate", default_rate))
        superframe = md.get("superframe")

        p = Parameter(
            name=name,
            start_bit=0,  # 717 uses word/bit_offset, not absolute
            bit_length=length,
            data_type="DISCRETE",
            rate=rate,
            subframe=subframe,
            word=word,
            bit_offset=bit_offset,
            superframe=superframe,
        )
        out[name] = p

    return out


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
    """ARINC 767 VEC parser."""
    text = path.read_text(encoding="utf-8").strip()

    # JSON shortcut
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    out: dict[str, Any] = {}

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        name = parts[0]
        entry: dict[str, Any] = {
            "frame_id_767": None,
            "cob_formula": None,
        }

        # bitrange
        for tok in parts[1:]:
            br = _parse_bitrange_767(tok)
            if br:
                entry.update(br)
                break

        # rate
        for tok in reversed(parts):
            try:
                entry["rate"] = float(tok)
                break
            except Exception:
                continue
        entry.setdefault("rate", 1.0)

        # FID=
        for tok in parts:
            if tok.upper().startswith("FID="):
                try:
                    entry["frame_id_767"] = int(tok.split("=")[1])
                except Exception:
                    pass

        # COB=
        for tok in parts:
            if tok.upper().startswith("COB="):
                entry["cob_formula"] = tok.split("=", 1)[1]

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

        start_bit = word * 32 + bit_offset

        p = Parameter(
            name=name,
            start_bit=start_bit,
            bit_length=length,
            data_type="DISCRETE",
            rate=rate,
            frame_id_767=frame_id_767,
            cob_formula=cob_formula,
        )

        out[name] = p

    return out


def parse_vec_file(path: Path) -> dict[str, Any]:
    """Default parser = ARINC 717 (legacy)."""
    return parse_vec_file_717(path)


def vec_to_parameters(
    mapping: dict[str, Any], default_rate: float = 1.0
) -> dict[str, Parameter]:
    """Default converter = ARINC 717 (legacy)."""
    return vec_to_parameters_717(mapping, default_rate)
