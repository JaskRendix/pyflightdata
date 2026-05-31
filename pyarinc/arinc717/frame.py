from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Subframe:
    raw_bits: bytes
    subframe_index: int


@dataclass
class Frame:
    frame_index: int
    frame_bit_offset: int
    subframes: list[Subframe]
    words_per_subframe: int = 4
    word_bits: int = 12

    @property
    def bits(self) -> bytes:
        """Return the concatenated raw bits for the whole frame as bytes."""
        return b"".join(s.raw_bits for s in self.subframes)
