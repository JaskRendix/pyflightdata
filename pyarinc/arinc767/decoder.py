from __future__ import annotations

import logging
import struct
from collections.abc import Iterable
from typing import Any

import pandas as pd

from ..models.parameter import Parameter
from .frame import Arinc767Frame

logger = logging.getLogger(__name__)


class Arinc767Decoder:
    """Decode ARINC 767 frames into a pandas DataFrame with scheduling."""

    def __init__(self, params: Iterable[Parameter]):
        self.params = list(params)

    def decode_frames(self, frames: Iterable[Arinc767Frame]) -> pd.DataFrame:
        """Decode frames into a basic DataFrame.

        Returns columns: frame_index, frame_id, timestamp, parameter_name, value, valid
        """
        rows: list[dict[str, Any]] = []
        for frame in frames:
            row: dict[str, Any] = {
                "frame_index": frame.frame_index,
                "frame_id": frame.frame_id,
                "timestamp": frame.timestamp_str,
            }
            for p in self.params:
                # skip frame type/id doesn't match this parameter's frame
                if hasattr(p, "frame_id_767") and p.frame_id_767 != frame.frame_id:
                    continue
                value, valid = self._decode_parameter(frame, p)
                row[p.name] = value
                row[f"{p.name}_valid"] = valid
            rows.append(row)
        return pd.DataFrame(rows)

    def decode(
        self, frames: Iterable[Arinc767Frame], frames_per_second: int = 1
    ) -> pd.DataFrame:
        """Decode parameters with scheduling and rate expansion.

        Returns columns: time, parameter_name, value, frame_index, frame_id, valid
        """
        rows: list[dict[str, Any]] = []
        for frame in frames:
            # compute time from frame index and frames_per_second
            time = frame.frame_index / frames_per_second

            for p in self.params:
                # skip if frame_id doesn't match
                if hasattr(p, "frame_id_767") and p.frame_id_767 != frame.frame_id:
                    continue

                # rate-based sampling
                if p.rate <= 0:
                    continue
                interval_frames = max(1, int(round(frames_per_second / p.rate)))
                if (frame.frame_index % interval_frames) != 0:
                    rows.append(
                        {
                            "time": time,
                            "parameter_name": p.name,
                            "value": None,
                            "frame_index": frame.frame_index,
                            "frame_id": frame.frame_id,
                            "valid": False,
                        }
                    )
                    continue

                # decode parameter
                value, valid = self._decode_parameter(frame, p)
                rows.append(
                    {
                        "time": time,
                        "parameter_name": p.name,
                        "value": value,
                        "frame_index": frame.frame_index,
                        "frame_id": frame.frame_id,
                        "valid": valid,
                    }
                )

        return pd.DataFrame(rows)

    def _decode_parameter(
        self, frame: Arinc767Frame, param: Parameter
    ) -> tuple[Any, bool]:
        """Decode a single parameter from a frame.

        Returns (value, valid) tuple.
        """
        data = frame.data
        if not data:
            return (None, False)

        # compute byte and bit offset
        start_bit = param.compute_absolute_bit_start(1, 32)  # word_bits=32 for 767
        byte_offset = start_bit // 8
        bit_offset = start_bit % 8

        # validate bounds
        byte_len = (param.bit_length + 7) // 8
        if byte_offset + byte_len > len(data):
            return (None, False)

        try:
            # extract bits
            if param.bit_length <= 32:
                # single dword extraction
                raw = self._extract_bits_767(
                    data, byte_offset, bit_offset, param.bit_length
                )
            else:
                # multi-dword COB extraction
                raw = self._extract_bits_767(
                    data, byte_offset, bit_offset, param.bit_length
                )

            # decode using parameter's decode method
            value = param.decode(raw)
            return (value, True)
        except Exception as e:
            logger.debug(f"Failed to decode {param.name}: {e}")
            return (None, False)

    @staticmethod
    def _extract_bits_767(
        data: bytes, byte_offset: int, bit_offset: int, length: int
    ) -> int:
        """Extract bits from ARINC 767 frame data (big-endian).

        Args:
            data: frame data bytes
            byte_offset: byte index
            bit_offset: bit offset within the byte (MSB=0)
            length: number of bits to extract

        Returns:
            integer value
        """
        if length > 32:
            # COB: multi-dword extraction
            result = 0
            bits_read = 0
            while bits_read < length and byte_offset < len(data):
                byte_val = data[byte_offset]
                bits_avail = 8 - bit_offset
                bits_to_read = min(bits_avail, length - bits_read)
                mask = (1 << bits_to_read) - 1
                bits = (byte_val >> (bits_avail - bits_to_read)) & mask
                result = (result << bits_to_read) | bits
                bits_read += bits_to_read
                byte_offset += 1
                bit_offset = 0
            return result
        else:
            # standard single dword
            dword_idx = byte_offset // 4
            dword_offset = byte_offset % 4
            if dword_idx * 4 + 4 <= len(data):
                dword = struct.unpack(">I", data[dword_idx * 4 : (dword_idx + 1) * 4])[
                    0
                ]
            else:
                # partial dword at end
                remaining = len(data) - dword_idx * 4
                if remaining <= 0:
                    return 0
                padded = data[dword_idx * 4 :] + b"\x00" * (4 - remaining)
                dword = struct.unpack(">I", padded[:4])[0]

            bit_start = dword_offset * 8 + bit_offset
            shift = 32 - bit_start - length
            if shift >= 0:
                mask = (1 << length) - 1
                return (dword >> shift) & mask
            else:
                # spans dwords, need two reads
                mask1 = (1 << (32 - bit_start)) - 1
                val1 = (dword & mask1) << (-shift)
                if (dword_idx + 1) * 4 + 4 <= len(data):
                    dword2 = struct.unpack(
                        ">I", data[(dword_idx + 1) * 4 : (dword_idx + 2) * 4]
                    )[0]
                    mask2 = (1 << (-shift)) - 1
                    val2 = (dword2 >> (32 + shift)) & mask2
                    return val1 | val2
                else:
                    return val1
