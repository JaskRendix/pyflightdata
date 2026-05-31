from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class Frame:
    index: int
    bits: bytes
    samples: Sequence[int]

    def as_bitstring(self) -> str:
        return "".join(f"{b:08b}" for b in self.bits)
