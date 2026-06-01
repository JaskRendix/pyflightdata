from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import pandas as pd

from ..models.parameter import Parameter
from .frame import Arinc767Frame, Arinc767FrameParser

logger = logging.getLogger(__name__)


class Arinc767Decoder:
    """Decode ARINC 767 frames into a pandas DataFrame with scheduling."""

    def __init__(self, params: Iterable[Parameter], frames_per_second: float = 1.0):
        """Initialize the decoder.

        Args:
            params: Iterable of Parameter definitions.
            frames_per_second: Frame rate used to compute time axis.
        """
        self.params = list(params)
        self.frames_per_second = frames_per_second

    def decode_frames(self, frames: Iterable[Arinc767Frame]) -> pd.DataFrame:
        """Decode frames into a wide DataFrame.

        Returns columns:
            - frame_index
            - frame_id
            - timestamp
            - <param_name>
            - <param_name>_valid
        """
        rows: list[dict[str, Any]] = []

        for frame in frames:
            row: dict[str, Any] = {
                "frame_index": frame.frame_index,
                "frame_id": frame.frame_id,
                "timestamp": frame.timestamp_str,
            }

            data = frame.data
            if not data:
                logger.debug(
                    "Empty data section for frame %d (id=%d)",
                    frame.frame_index,
                    frame.frame_id,
                )
                rows.append(row)
                continue

            for p in self.params:
                # If parameter is bound to a specific 767 frame id, enforce it
                if getattr(p, "frame_id_767", None) is not None:
                    if p.frame_id_767 != frame.frame_id:
                        continue

                value, valid = self._decode_parameter_from_data(data, p)
                row[p.name] = value
                row[f"{p.name}_valid"] = valid

            rows.append(row)

        return pd.DataFrame(rows)

    def decode(self, data: bytes | Iterable[Arinc767Frame]) -> pd.DataFrame:
        """Decode raw bytes into a scheduled, long-format DataFrame.

        Uses Arinc767FrameParser.iter_frames() to parse frames.

        Returns columns:
            - time          (float, seconds from start)
            - parameter_name
            - value
            - frame_index
            - frame_id
            - valid
        """

        # Allow override of fps per call
        fps = self.frames_per_second

        # Case 1: raw bytes → parse frames
        if isinstance(data, (bytes, bytearray)):
            frames = Arinc767FrameParser.iter_frames(data)

        # Case 2: already a list/iterable of frames
        else:
            frames = data

        rows: list[dict[str, Any]] = []

        for frame_index, frame in enumerate(frames):
            frame_time = frame_index / fps
            frame_data = frame.data

            # If no data, still emit invalid scheduled rows
            if not frame_data:
                for p in self.params:
                    if getattr(p, "frame_id_767", None) not in (None, frame.frame_id):
                        continue
                    if p.rate <= 0:
                        continue
                    rows.append(
                        {
                            "time": frame_time,
                            "parameter_name": p.name,
                            "value": None,
                            "frame_index": frame.frame_index,
                            "frame_id": frame.frame_id,
                            "valid": False,
                        }
                    )
                continue

            for p in self.params:
                # Frame ID filter
                if getattr(p, "frame_id_767", None) not in (None, frame.frame_id):
                    continue

                # Rate-based scheduling
                if p.rate <= 0:
                    continue

                interval_frames = max(1, int(round(fps / p.rate)))
                should_sample = (frame_index % interval_frames) == 0

                if not should_sample:
                    rows.append(
                        {
                            "time": frame_time,
                            "parameter_name": p.name,
                            "value": None,
                            "frame_index": frame.frame_index,
                            "frame_id": frame.frame_id,
                            "valid": False,
                        }
                    )
                    continue

                value, valid = self._decode_parameter_from_data(frame_data, p)
                rows.append(
                    {
                        "time": frame_time,
                        "parameter_name": p.name,
                        "value": value,
                        "frame_index": frame.frame_index,
                        "frame_id": frame.frame_id,
                        "valid": valid,
                    }
                )

        return pd.DataFrame(rows)

    def _decode_parameter_from_data(
        self, data: bytes, param: Parameter
    ) -> tuple[Any, bool]:
        """Decode a single parameter from a frame data section.

        Returns:
            (value, valid)
        """
        try:
            value = param.decode_raw_from_bytes(data)
            return value, True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to decode parameter %s: %s", param.name, exc)
            return None, False
