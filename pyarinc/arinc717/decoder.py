from collections.abc import Iterable
from typing import Any

import pandas as pd

from ..models.parameter import Parameter
from .frame import Frame


class Arinc717Decoder:
    """Decode ARINC 717 frames into a pandas DataFrame.

    The decoder receives `Frame` objects produced by `AlignedStream` and
    decodes parameters by delegating to `Parameter.decode_from_bytes`.
    Decoded rows include frame metadata required for scheduling.
    """

    def __init__(self, params: Iterable[Parameter]):
        self.params = list(params)

    def decode(self, aligned_stream, frames_per_second: int = 16) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        words_per_subframe = aligned_stream.words_per_subframe
        word_bits = aligned_stream.word_bits

        for frame in aligned_stream.iter_frames():
            frame_index = frame.frame_index
            time = frame_index / frames_per_second

            for p in self.params:
                if p.rate <= 0:
                    continue

                interval_frames = int(round(frames_per_second / p.rate))
                if interval_frames <= 0:
                    interval_frames = 1

                # superframe scheduling
                current_sf = frame_index % p.superframe_group_count
                if p.superframe is not None and current_sf != p.superframe:
                    rows.append(
                        {
                            "time": time,
                            "parameter_name": p.name,
                            "value": None,
                            "frame_index": frame_index,
                            "subframe_index": p.subframe,
                            "superframe_index": current_sf,
                            "bit_offset": p.bit_offset,
                            "valid": False,
                        }
                    )
                    continue

                # rate scheduling
                if (frame_index % interval_frames) != 0:
                    rows.append(
                        {
                            "time": time,
                            "parameter_name": p.name,
                            "value": None,
                            "frame_index": frame_index,
                            "subframe_index": p.subframe,
                            "superframe_index": current_sf,
                            "bit_offset": p.bit_offset,
                            "valid": False,
                        }
                    )
                    continue

                # decode
                value, valid = p.decode_from_frame(
                    frame.bits, words_per_subframe, word_bits
                )

                rows.append(
                    {
                        "time": time,
                        "parameter_name": p.name,
                        "value": value,
                        "frame_index": frame_index,
                        "subframe_index": p.subframe,
                        "superframe_index": current_sf,
                        "bit_offset": p.bit_offset,
                        "valid": valid,
                    }
                )

        return pd.DataFrame(rows)

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

            # ARINC 717 uses subframe/word/bit_offset
            for p in self.params:
                value, valid = p.decode_from_frame(
                    frame.bits,
                    frame.words_per_subframe,
                    frame.word_bits,
                )
                row[p.name] = value

            rows.append(row)

        return pd.DataFrame(rows)
