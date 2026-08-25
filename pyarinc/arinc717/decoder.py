from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import pandas as pd

from ..models.parameter import Parameter
from .aligned import AlignedStream
from .frame import Frame

logger = logging.getLogger(__name__)


class Arinc717Decoder:
    """Decode ARINC 717 frames into a pandas DataFrame.

    The decoder receives `Frame` objects produced by `AlignedStream` and
    decodes parameters by delegating to `Parameter.decode_from_frame`.
    Decoded rows include frame metadata required for scheduling.
    """

    def __init__(self, params: Iterable[Parameter]):
        self.params = list(params)

        # Pre-filter valid parameters
        self._valid_params = [
            p for p in self.params if p.rate is not None and p.rate > 0
        ]

        # Cache bound decode functions per parameter using id(p)
        self._decode_funcs = {id(p): p.decode_from_frame for p in self._valid_params}

        # Cache superframe, subframe, and attribute lookups using id(p)
        self._superframe_counts = {
            id(p): getattr(p, "superframe_group_count", 1) for p in self._valid_params
        }
        self._superframes = {
            id(p): getattr(p, "superframe", None) for p in self._valid_params
        }
        self._subframes = {
            id(p): getattr(p, "subframe", None) for p in self._valid_params
        }
        self._bit_offsets = {
            id(p): getattr(p, "bit_offset", 0) for p in self._valid_params
        }

        # Refinement A (Part 1): Check if parameters are trivially scheduled (no superframes, rates match fps assuming 16fps default or custom)
        # We can dynamically evaluate trivial scheduling during decode() when fps is known,
        # but we can cache whether any superframes exist upfront:
        self._has_superframes = any(
            self._superframes[id(p)] is not None for p in self._valid_params
        )

    def decode_raw_bytes(
        self,
        data: bytes,
        frames_per_second: int = 16,
        word_bits: int = 12,
        subframes_per_frame: int = 4,
        words_per_subframe: int = 64,
        sync_pattern: int = 0x257,
        sync_length: int = 12,
    ) -> pd.DataFrame:
        """Parse raw bytes into an aligned stream via bitstream synchronization and decode them."""
        # Use from_bitstream to correctly convert raw bytes into ArincFrame objects
        aligned_stream = AlignedStream.from_bitstream(
            data=data,
            sync_pattern=sync_pattern,
            sync_length=sync_length,
            word_bits=word_bits,
            words_per_subframe=words_per_subframe,
            subframes_per_frame=subframes_per_frame,
        )
        return self.decode(aligned_stream, frames_per_second=frames_per_second)

    def decode(self, aligned_stream, frames_per_second: int = 16) -> pd.DataFrame:
        words_per_subframe = aligned_stream.words_per_subframe
        word_bits = aligned_stream.word_bits

        # Cache interval_frames per parameter based on frames_per_second using id(p)
        interval_frames_map = {
            id(p): max(1, int(round(frames_per_second / p.rate)))
            for p in self._valid_params
        }

        # Fast-path for trivially scheduled parameters
        is_trivially_scheduled = not self._has_superframes and all(
            p.rate == frames_per_second for p in self._valid_params
        )

        frames = list(aligned_stream.iter_frames())
        if not frames:
            logger.warning(
                "No ARINC 717 frames found or sync pattern not matched. Returning empty DataFrame."
            )
            return pd.DataFrame(
                columns=[
                    "time",
                    "parameter_name",
                    "value",
                    "frame_index",
                    "subframe_index",
                    "superframe_index",
                    "bit_offset",
                    "valid",
                ]
            )

        times: list[float] = []
        param_names: list[str] = []
        values: list[Any] = []
        frame_indices: list[int] = []
        subframe_indices: list[Any] = []
        superframe_indices: list[Any] = []
        bit_offsets: list[Any] = []
        valids: list[bool] = []

        for frame_index, frame in enumerate(frames):
            time = frame_index / frames_per_second
            frame_bits = getattr(frame, "bits", None)
            f_idx = getattr(frame, "frame_index", frame_index)

            if frame_bits is None:
                continue

            # Fast-path execution loop
            if is_trivially_scheduled:
                for p in self._valid_params:
                    try:
                        decode_func = self._decode_funcs[id(p)]
                        value, valid = decode_func(
                            frame_bits, words_per_subframe, word_bits
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Failed to decode parameter %s: %s", p.name, exc)
                        value, valid = None, False

                    times.append(time)
                    param_names.append(p.name)
                    values.append(value)
                    frame_indices.append(f_idx)
                    subframe_indices.append(self._subframes[id(p)])
                    superframe_indices.append(0)
                    bit_offsets.append(self._bit_offsets[id(p)])
                    valids.append(valid)
                continue

            # Standard scheduled loop
            for p in self._valid_params:
                p_id = id(p)
                interval_frames = interval_frames_map[p_id]
                sf_count = self._superframe_counts[p_id]
                sf_target = self._superframes[p_id]
                sub_idx = self._subframes[p_id]
                bit_off = self._bit_offsets[p_id]

                # superframe scheduling
                current_sf = f_idx % sf_count
                if sf_target is not None and current_sf != sf_target:
                    times.append(time)
                    param_names.append(p.name)
                    values.append(None)
                    frame_indices.append(f_idx)
                    subframe_indices.append(sub_idx)
                    superframe_indices.append(current_sf)
                    bit_offsets.append(bit_off)
                    valids.append(False)
                    continue

                # rate scheduling
                if (f_idx % interval_frames) != 0:
                    times.append(time)
                    param_names.append(p.name)
                    values.append(None)
                    frame_indices.append(f_idx)
                    subframe_indices.append(sub_idx)
                    superframe_indices.append(current_sf)
                    bit_offsets.append(bit_off)
                    valids.append(False)
                    continue

                # decode using cached bound function
                try:
                    decode_func = self._decode_funcs[p_id]
                    value, valid = decode_func(
                        frame_bits, words_per_subframe, word_bits
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "Failed to decode ARINC 717 parameter %s: %s", p.name, exc
                    )
                    value, valid = None, False

                times.append(time)
                param_names.append(p.name)
                values.append(value)
                frame_indices.append(f_idx)
                subframe_indices.append(sub_idx)
                superframe_indices.append(current_sf)
                bit_offsets.append(bit_off)
                valids.append(valid)

        return pd.DataFrame(
            {
                "time": times,
                "parameter_name": param_names,
                "value": values,
                "frame_index": frame_indices,
                "subframe_index": subframe_indices,
                "superframe_index": superframe_indices,
                "bit_offset": bit_offsets,
                "valid": valids,
            }
        )

    def decode_frames(self, frames: Iterable[Frame]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for frame in frames:
            frame_index = getattr(frame, "frame_index", None)
            if frame_index is None:
                frame_index = getattr(frame, "index", None)

            bit_offset = getattr(frame, "frame_bit_offset", None)
            if bit_offset is None:
                bit_offset = getattr(frame, "bit_offset", 0)

            row: dict[str, Any] = {
                "frame_index": frame_index,
                "bit_offset": bit_offset,
            }

            frame_bits = getattr(frame, "bits", None)
            w_sub = getattr(frame, "words_per_subframe", None)
            w_bits = getattr(frame, "word_bits", None)

            for p in self._valid_params:
                try:
                    decode_func = self._decode_funcs[id(p)]
                    value, valid = decode_func(frame_bits, w_sub, w_bits)
                    row[p.name] = value
                    row[f"{p.name}_valid"] = valid
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "Failed to decode wide frame parameter %s: %s", p.name, exc
                    )
                    row[p.name] = None
                    row[f"{p.name}_valid"] = False

            rows.append(row)

        return pd.DataFrame(rows)
