from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass

from .bitstream import BitstreamScanner
from .frame import Frame as ArincFrame
from .frame import Subframe

logger = logging.getLogger(__name__)


@dataclass
class AlignedStream:
    frames: list[ArincFrame]
    word_bits: int
    subframes_per_frame: int
    words_per_subframe: int

    @classmethod
    def from_bitstream(
        cls,
        data: bytes,
        sync_pattern: int,
        sync_length: int,
        word_bits: int = 12,
        words_per_subframe: int = 256,
        subframes_per_frame: int = 4,
        sample_rate_hz: float | None = None,
    ) -> "AlignedStream":
        """Build an AlignedStream by finding sync positions and slicing frames.

        The method looks for sync occurrences and then slices fixed-size frames
        from the first sync onward. For simplicity we assume a frame is:
            frame_bits = word_bits * words_per_subframe * subframes_per_frame
        """
        scanner = BitstreamScanner(sync_pattern, sync_length)
        positions = scanner.find_sync_positions(data)
        logger.debug("Sync positions: %s", positions)
        frames: list[ArincFrame] = []
        if not positions:
            return cls(
                frames=frames,
                word_bits=word_bits,
                subframes_per_frame=subframes_per_frame,
                words_per_subframe=words_per_subframe,
            )
        frame_bits = word_bits * words_per_subframe * subframes_per_frame
        # convert bits to bytes length
        frame_bytes = (frame_bits + 7) // 8
        # Start from first sync position (bit offset)
        bit_offset = positions[0]
        byte_offset = bit_offset // 8
        # iterate while enough data for a frame remains
        frame_idx = 0
        while byte_offset + frame_bytes <= len(data):
            chunk = data[byte_offset : byte_offset + frame_bytes]
            # split into subframes
            sf_bytes = (word_bits * words_per_subframe + 7) // 8
            subframes: list[Subframe] = []
            for si in range(subframes_per_frame):
                start = si * sf_bytes
                sub = chunk[start : start + sf_bytes]
                subframes.append(Subframe(raw_bits=sub, subframe_index=si))
            frames.append(
                ArincFrame(
                    frame_index=frame_idx,
                    frame_bit_offset=byte_offset * 8,
                    subframes=subframes,
                )
            )
            frame_idx += 1
            byte_offset += frame_bytes
        return cls(
            frames=frames,
            word_bits=word_bits,
            subframes_per_frame=subframes_per_frame,
            words_per_subframe=words_per_subframe,
        )

    def iter_frames(self) -> Iterator[ArincFrame]:
        for f in self.frames:
            yield f
