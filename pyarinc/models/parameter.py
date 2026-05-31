from dataclasses import dataclass
from typing import Any

from ..utils.bitops import extract_bits


@dataclass
class Parameter:
    name: str
    start_bit: int
    bit_length: int
    data_type: str  # 'BNR', 'BCD', 'DISCRETE', 'CHAR', 'UTC', 'PACKED', 'COB'
    scale: float | None = None
    offset: float | None = None
    signed: bool = False

    # Scheduling fields (ARINC 717)
    rate: float = 1.0
    subframe: int = 0
    word: int = 0
    bit_offset: int = 0
    superframe: int | None = None
    superframe_group_count: int = 4

    # ARINC 767-specific metadata
    frame_id_767: int | None = None
    cob_formula: str | None = None  # optional formula string from VEC/PRM

    def decode_raw_from_bytes(self, data: bytes) -> Any:
        """Decode using absolute start_bit (used for ARINC 767)."""
        raw = extract_bits(data, self.start_bit, self.bit_length, signed=self.signed)
        return self.decode(raw)

    def compute_absolute_bit_start(
        self, words_per_subframe: int, word_bits: int
    ) -> int:
        """Compute MSB-indexed bit start for ARINC 717 frames."""
        subframe_bits = words_per_subframe * word_bits
        return self.subframe * subframe_bits + self.word * word_bits + self.bit_offset

    def decode_from_frame(
        self, frame_bytes: bytes, words_per_subframe: int, word_bits: int
    ) -> tuple[Any, bool]:
        """Decode this parameter from a full frame bytes buffer.

        If start_bit is provided, use it directly (simple tests).
        Otherwise compute from subframe/word/bit_offset (real ARINC 717).
        """

        # If start_bit is explicitly set, use it
        if self.start_bit is not None:
            start = self.start_bit
        else:
            start = self.compute_absolute_bit_start(words_per_subframe, word_bits)

        total_bits = len(frame_bytes) * 8
        if start < 0 or (start + self.bit_length) > total_bits:
            return (None, False)

        raw = extract_bits(frame_bytes, start, self.bit_length, signed=self.signed)
        return (self.decode(raw), True)

    def decode(self, raw_bits: int) -> Any:
        """Decode raw integer bits according to ARINC data type."""
        if self.data_type == "BNR":
            return self._decode_bnr(raw_bits)

        if self.data_type == "DISCRETE":
            return self._decode_discrete(raw_bits)

        if self.data_type == "BCD":
            return self._decode_bcd(raw_bits)

        if self.data_type in ("CHAR", "ASCII", "ISO"):
            return self._decode_char(raw_bits)

        if self.data_type == "UTC":
            return self._decode_utc(raw_bits)

        if self.data_type == "PACKED":
            return int(raw_bits)

        if self.data_type == "COB":
            return self._decode_cob(raw_bits)

        return raw_bits

    def _decode_bnr(self, raw_bits: int) -> float:
        if self.signed:
            sign_bit = 1 << (self.bit_length - 1)
            if raw_bits & sign_bit:
                raw_bits = raw_bits - (1 << self.bit_length)

        val = float(raw_bits)
        if self.scale is not None:
            val *= self.scale
        if self.offset is not None:
            val += self.offset
        return val

    def _decode_discrete(self, raw_bits: int) -> Any:
        if self.bit_length == 1:
            return bool(raw_bits)
        return int(raw_bits)

    def _decode_bcd(self, raw_bits: int) -> str:
        if raw_bits == 0:
            return "0"
        digits = []
        n = raw_bits
        while n > 0:
            digits.append(str(n & 0xF))
            n >>= 4
        return "".join(reversed(digits))

    def _decode_char(self, raw_bits: int) -> str:
        byte_len = (self.bit_length + 7) // 8
        b = int(raw_bits).to_bytes(byte_len, "big")
        return b.rstrip(b"\x00").decode("ascii", errors="replace")

    def _decode_utc(self, raw_bits: int) -> str:
        s = str(self._bcd_from_int(raw_bits)).rjust(6, "0")
        hh = int(s[0:2])
        mm = int(s[2:4])
        ss = int(s[4:6])
        return f"{hh:02d}:{mm:02d}:{ss:02d}"

    def _decode_cob(self, raw_bits: int) -> Any:
        """
        ARINC 767 COB (Computed On Board) parameters may require formulas.
        If a formula is provided in the config, evaluate it safely.
        Otherwise return the raw integer.
        """
        if self.cob_formula:
            # Safe evaluation context: only raw_bits, scale, offset allowed
            ctx = {
                "raw": raw_bits,
                "scale": self.scale or 1.0,
                "offset": self.offset or 0.0,
            }
            try:
                return eval(self.cob_formula, {"__builtins__": {}}, ctx)
            except Exception:
                return raw_bits

        return raw_bits

    @staticmethod
    def _bcd_from_int(value: int) -> int:
        out = 0
        multiplier = 1
        v = value
        while v > 0:
            digit = v & 0xF
            out = digit * multiplier + out
            multiplier *= 10
            v >>= 4
        return out
