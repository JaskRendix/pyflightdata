from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models.parameter import Parameter

logger = logging.getLogger(__name__)


def parse_prm_file(path: Path) -> dict[str, Any]:
    """Parse a PRM file into a mapping of parameter definitions.

    Supported line formats (space-separated):
      name subframe word bit_offset length rate [superframe] [KEY=VALUE ...]
    Also accepts a JSON file mapping parameter names to definitions.
    """
    out: dict[str, Any] = {}

    try:
        text = path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.error(f"Failed to read PRM file {path}: {e}")
        raise

    # Try parsing as JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        else:
            logger.warning(
                f"PRM file {path} contains valid JSON, but the root element is not a dictionary. Falling back to text line parsing."
            )
    except json.JSONDecodeError:
        pass  # Not JSON, fall back to text line parsing

    for line_num, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 6:
            logger.warning(
                f"Skipping malformed line {line_num} in {path}: insufficient fields"
            )
            continue

        try:
            name = parts[0]
            subframe = int(parts[1])
            word = int(parts[2])
            bit_offset = int(parts[3])
            length = int(parts[4])
            rate = float(parts[5])

            superframe = None
            start_idx = 6

            # Check if the 7th token is a superframe integer or a keyword
            if len(parts) > 6 and "=" not in parts[6]:
                try:
                    superframe = int(parts[6])
                    start_idx = 7
                except ValueError:
                    pass

            param_meta: dict[str, Any] = {
                "subframe": subframe,
                "word": word,
                "bit_offset": bit_offset,
                "length": length,
                "rate": rate,
                "superframe": superframe,
            }

            # Parse optional trailing key-value tokens (e.g., TYPE=BNR SCALE=0.1)
            line_has_error = False
            for part in parts[start_idx:]:
                if "=" in part:
                    key, val = part.split("=", 1)
                    key = key.strip().lower()
                    val = val.strip()

                    if key == "type":
                        param_meta["type"] = val
                    elif key == "scale":
                        try:
                            param_meta["scale"] = float(val)
                        except ValueError:
                            logger.warning(
                                f"Invalid scale value '{val}' on line {line_num} in {path}"
                            )
                            line_has_error = True
                            break
                    elif key == "offset":
                        try:
                            param_meta["offset"] = float(val)
                        except ValueError:
                            logger.warning(
                                f"Invalid offset value '{val}' on line {line_num} in {path}"
                            )
                            line_has_error = True
                            break

            if line_has_error:
                continue

            out[name] = param_meta

        except Exception as e:
            logger.warning(f"Error parsing line {line_num} in {path}: {e}")
            continue

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
