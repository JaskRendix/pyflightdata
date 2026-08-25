from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import pandas as pd

from ..models.parameter import Parameter
from .frame import Arinc767Frame
from .parser import Arinc767FrameParser

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

        # Pre-filter valid parameters
        self._valid_params = [
            p for p in self.params if p.rate is not None and p.rate > 0
        ]

        # Check for frame ID filters
        self._has_frame_filters = any(
            getattr(p, "frame_id_767", None) is not None for p in self._valid_params
        )

        # Refinement 1: Cache frame_id_767 attribute lookups per parameter using id(p)
        self._frame_ids = {
            id(p): getattr(p, "frame_id_767", None) for p in self._valid_params
        }

        # Refinement 2: Cache bound decode functions per parameter using id(p)
        self._decode_funcs = {
            id(p): p.decode_raw_from_bytes for p in self._valid_params
        }

        # Cache interval_frames per parameter using id(p)
        self._interval_frames = {
            id(p): max(1, int(round(self.frames_per_second / p.rate)))
            for p in self._valid_params
        }

        # Fast-path check (no frame filters AND all parameter rates match fps)
        self._is_trivially_scheduled = not self._has_frame_filters and all(
            p.rate == self.frames_per_second for p in self._valid_params
        )

    def decode_frames(self, frames: Iterable[Arinc767Frame]) -> pd.DataFrame:
        """Decode frames into a wide DataFrame."""
        rows: list[dict[str, Any]] = []

        for frame in frames:
            row: dict[str, Any] = {
                "frame_index": frame.frame_index,
                "frame_id": frame.frame_id,
                "timestamp": frame.timestamp_str,
                "timestamp_ms": frame.timestamp_ms,
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

            for p in self._valid_params:
                p_id = id(p)
                if self._has_frame_filters and self._frame_ids[p_id] not in (
                    None,
                    frame.frame_id,
                ):
                    continue

                value, valid = self._decode_parameter_from_data(p, data)
                row[p.name] = value
                row[f"{p.name}_valid"] = valid

            rows.append(row)

        return pd.DataFrame(rows)

    def decode_raw_bytes(self, data: bytes, **kwargs: Any) -> pd.DataFrame:
        """Public helper to parse raw bytes into frames and decode them."""
        frames = Arinc767FrameParser.iter_frames(data, **kwargs)
        return self.decode(frames)

    def decode(
        self, data: bytes | Iterable[Arinc767Frame], **kwargs: Any
    ) -> pd.DataFrame:
        """Decode raw bytes or frames into a scheduled, long-format DataFrame."""
        fps = self.frames_per_second

        # Case 1: raw bytes → parse frames via helper (passing down kwargs)
        if isinstance(data, (bytes, bytearray)):
            frames = list(Arinc767FrameParser.iter_frames(data, **kwargs))
        else:
            frames = list(data)

        # Refinement 3: Fast-path for entirely empty or corrupted data blocks (no frames have data)
        if frames and all(not f.data for f in frames):
            logger.warning(
                "All frames contain empty data sections. Returning empty/invalid scheduled DataFrame."
            )

        times: list[float] = []
        param_names: list[str] = []
        values: list[Any] = []
        frame_indices: list[int] = []
        frame_ids: list[int] = []
        valids: list[bool] = []

        for frame_index, frame in enumerate(frames):
            frame_time = (
                frame.timestamp_ms / 1000.0
                if frame.timestamp_ms is not None
                else frame_index / fps
            )
            frame_data = frame.data
            f_id = frame.frame_id
            f_idx = frame.frame_index

            # Fast-path for trivially scheduled parameters
            if self._is_trivially_scheduled:
                if not frame_data:
                    for p in self._valid_params:
                        times.append(frame_time)
                        param_names.append(p.name)
                        values.append(None)
                        frame_indices.append(f_idx)
                        frame_ids.append(f_id)
                        valids.append(False)
                    continue

                for p in self._valid_params:
                    value, valid = self._decode_parameter_from_data(p, frame_data)
                    times.append(frame_time)
                    param_names.append(p.name)
                    values.append(value)
                    frame_indices.append(f_idx)
                    frame_ids.append(f_id)
                    valids.append(valid)
                continue

            # Standard scheduled loop with cached lookups
            for p in self._valid_params:
                p_id = id(p)
                if self._has_frame_filters and self._frame_ids[p_id] not in (
                    None,
                    f_id,
                ):
                    continue

                interval_frames = self._interval_frames[p_id]
                should_sample = (frame_index % interval_frames) == 0

                if not frame_data or not should_sample:
                    times.append(frame_time)
                    param_names.append(p.name)
                    values.append(None)
                    frame_indices.append(f_idx)
                    frame_ids.append(f_id)
                    valids.append(False)
                    continue

                value, valid = self._decode_parameter_from_data(p, frame_data)
                times.append(frame_time)
                param_names.append(p.name)
                values.append(value)
                frame_indices.append(f_idx)
                frame_ids.append(f_id)
                valids.append(valid)

        return pd.DataFrame(
            {
                "time": times,
                "parameter_name": param_names,
                "value": values,
                "frame_index": frame_indices,
                "frame_id": frame_ids,
                "valid": valids,
            }
        )

    def _decode_parameter_from_data(
        self, param: Parameter, data: bytes
    ) -> tuple[Any, bool]:
        """Decode a single parameter from a frame data section using cached functions."""
        try:
            decode_func = self._decode_funcs[id(param)]
            value = decode_func(data)
            return value, True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to decode parameter %s: %s", param.name, exc)
            return None, False
