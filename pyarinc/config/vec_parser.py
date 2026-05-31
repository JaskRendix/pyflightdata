import json
import re
from pathlib import Path
from typing import Any

from ..models.parameter import Parameter

_VEC_BITRANGE_RE = re.compile(
    r"W\s*(?P<word>\d+)\s*B\s*(?P<bstart>\d+)(?:-(?P<bend>\d+))?", re.IGNORECASE
)


def _parse_bitrange(token: str) -> dict[str, int] | None:
    """Parse tokens like 'W12B3-7' or 'W12 B3-7' and return word, bit_offset, length."""
    m = _VEC_BITRANGE_RE.search(token)
    if not m:
        return None
    word = int(m.group("word"))
    bstart = int(m.group("bstart"))
    bend = m.group("bend")
    bend_i = int(bend) if bend is not None else bstart
    # convert to zero-based word index and zero-based bit offset (assume bits numbered MSB=0)
    bit_offset = bstart
    length = bend_i - bstart + 1
    return {"word": word - 1, "bit_offset": bit_offset, "length": length}


def parse_vec_file(path: Path) -> dict[str, Any]:
    """Parse a VEC file into a dict mapping parameter names to metadata.

    Supports JSON mapping or common textual VEC lines. Returns a mapping of
    parameter name -> metadata dict with keys: subframe, word, bit_offset, length, rate, superframe.
    """
    out: dict[str, Any] = {}
    text = path.read_text(encoding="utf-8").strip()
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
        # common VEC: NAME <other> W12B3-7 <type> <rate> ...
        parts = line.split()
        name = parts[0]
        entry: dict[str, Any] = {}
        # find bitrange token
        for tok in parts[1:6]:
            br = _parse_bitrange(tok)
            if br:
                entry.update(br)
                break
        # optional rate token (float)
        for tok in reversed(parts):
            try:
                entry["rate"] = float(tok)
                break
            except Exception:
                continue
        # optional superframe indicated by 'SF=n' or last integer token
        sf = None
        for tok in parts:
            if tok.upper().startswith("SF="):
                try:
                    sf = int(tok.split("=")[1])
                except Exception:
                    pass
        if sf is not None:
            entry["superframe"] = sf
        # default subframe 0 if not present
        entry.setdefault("subframe", 0)
        out[name] = entry
    return out


def vec_to_parameters(
    mapping: dict[str, Any], default_rate: float = 1.0
) -> dict[str, Parameter]:
    """Convert parsed vec mapping to Parameter objects.

    Returns dict name->Parameter.
    """
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
            start_bit=0,
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
