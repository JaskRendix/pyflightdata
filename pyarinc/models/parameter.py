from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ..utils.bitops import extract_bits

logger = logging.getLogger(__name__)


@dataclass
class Parameter:
    """Represents a single parameter from ARINC 717 or ARINC 767 data.

    Supports flexible bit-level extraction and decoding into various ARINC types:
    BNR (binary), BCD (binary-coded decimal), DISCRETE, CHAR/ASCII, UTC, PACKED, COB.

    Can be used in two modes:

    1. ARINC 767 (absolute bit indexing):
       - start_bit: absolute bit position in frame data (0-based MSB-first)
       - decode_raw_from_bytes(data) -> decoded_value

    2. ARINC 717 (word-based indexing):
       - subframe, word, bit_offset: locate parameter in frame structure
       - decode_from_frame(frame_bytes, ...) -> (decoded_value, valid)

    Note on start_bit:
        start_bit is intentionally Optional. 717-style parameters should leave
        it as None and rely on subframe/word/bit_offset; decode_from_frame()
        only falls back to computing the position from those fields when
        start_bit is None. Setting start_bit=0 on a 717 parameter (instead of
        leaving it None) silently forces decoding from bit 0 of the frame
        regardless of subframe/word/bit_offset -- do not do that.
    """

    name: str
    """Parameter identifier/name."""

    bit_length: int
    """Number of bits occupied by parameter (1-32)."""

    data_type: str
    """Data type: 'BNR', 'BCD', 'DISCRETE', 'CHAR', 'ASCII', 'UTC', 'PACKED', 'COB'."""

    start_bit: int | None = None
    """Absolute bit position (0-based, MSB-first). Required for ARINC 767
    (decode_raw_from_bytes). For ARINC 717, leave as None so
    decode_from_frame() computes the position from subframe/word/bit_offset."""

    scale: float | None = None
    """Scale factor for BNR decoding (multiplier)."""

    offset: float | None = None
    """Offset for BNR decoding (additive)."""

    signed: bool = False
    """If True, interpret BNR as two's complement signed integer."""

    # Scheduling fields (ARINC 717)
    rate: float = 1.0
    """Sampling rate in Hz (used by decoder for rate-based scheduling)."""

    subframe: int = 0
    """ARINC 717 subframe index."""

    word: int = 0
    """ARINC 717 word index within subframe."""

    bit_offset: int = 0
    """Bit offset within word (ARINC 717)."""

    superframe: int | None = None
    """Superframe index for multi-frame parameters (ARINC 717)."""

    superframe_group_count: int = 4
    """Number of frames in superframe group (ARINC 717)."""

    # ARINC 767-specific metadata
    frame_id_767: int | None = None
    """Frame ID indicating which frame contains this parameter (ARINC 767)."""

    cob_formula: str | None = None
    """Optional formula for COB (Computed On Board) parameters.

    Evaluated with restricted namespace: {"raw": <bit_value>, "scale": <scale>, "offset": <offset>}
    Example: "raw * 0.00390625" for Mach computation.
    """
    # ----------------------------------------------------------------------
    # Factory constructors
    # ----------------------------------------------------------------------

    @classmethod
    def from_717(
        cls,
        name: str,
        bit_length: int,
        data_type: str,
        *,
        subframe: int,
        word: int,
        bit_offset: int,
        rate: float = 1.0,
        scale: float | None = None,
        offset: float | None = None,
        signed: bool = False,
        superframe: int | None = None,
        superframe_group_count: int = 4,
    ) -> "Parameter":
        """
        Construct an ARINC 717 parameter.

        start_bit is intentionally left as None so decode_from_frame()
        computes the absolute bit position from subframe/word/bit_offset.
        """
        return cls(
            name=name,
            bit_length=bit_length,
            data_type=data_type,
            start_bit=None,  # critical: 717 parameters must NOT set start_bit
            scale=scale,
            offset=offset,
            signed=signed,
            rate=rate,
            subframe=subframe,
            word=word,
            bit_offset=bit_offset,
            superframe=superframe,
            superframe_group_count=superframe_group_count,
        )

    @classmethod
    def from_767(
        cls,
        name: str,
        bit_length: int,
        data_type: str,
        *,
        start_bit: int,
        frame_id_767: int | None = None,
        scale: float | None = None,
        offset: float | None = None,
        signed: bool = False,
        rate: float = 1.0,
        cob_formula: str | None = None,
    ) -> "Parameter":
        """
        Construct an ARINC 767 parameter.

        Requires an absolute start_bit (0-based MSB-first).
        """
        return cls(
            name=name,
            bit_length=bit_length,
            data_type=data_type,
            start_bit=start_bit,
            frame_id_767=frame_id_767,
            scale=scale,
            offset=offset,
            signed=signed,
            rate=rate,
            cob_formula=cob_formula,
        )

    def decode_raw_from_bytes(self, data: bytes) -> Any:
        """Decode from frame data using absolute start_bit (ARINC 767 style).

        Extracts bits from data using start_bit as absolute index, then decodes
        according to data_type. Used by Arinc767Decoder.

        Args:
            data: frame data section (bytes 10 onwards from ARINC 767 frame)

        Returns:
            Decoded value (float, int, str, bool, etc. depending on data_type)

        Raises:
            ValueError: if start_bit is not set, or extraction is out of bounds.
        """
        if self.start_bit is None:
            raise ValueError(
                f"Parameter {self.name}: start_bit is not set; "
                "decode_raw_from_bytes() requires an absolute start_bit "
                "(ARINC 767 style). Use decode_from_frame() for "
                "subframe/word/bit_offset-based (ARINC 717) parameters."
            )

        total_bits = len(data) * 8
        if self.start_bit < 0 or (self.start_bit + self.bit_length) > total_bits:
            raise ValueError(
                f"Parameter {self.name}: out of bounds (start={self.start_bit}, len={self.bit_length}, total={total_bits})"
            )

        raw = self.extract_bits_767(data, self.start_bit, self.bit_length, self.signed)
        return self.decode(raw)

    @staticmethod
    def extract_bits_767(
        data: bytes, start_bit: int, length: int, signed: bool = False
    ) -> int:
        """Extract bits using 0-based MSB-first indexing (ARINC 767 style).

        Supports arbitrary bit extraction including cross-byte boundaries.
        Does not require 32-bit alignment.

        Args:
            data: source bytes buffer
            start_bit: bit position (0 = MSB of byte 0)
            length: number of bits to extract (1-32)
            signed: if True, interpret as two's complement signed integer

        Returns:
            Integer value of extracted bits

        Example:
            data = b'\\x12\\x34\\x56'
            extract_bits_767(data, 0, 8)    # -> 0x12 (first byte)
            extract_bits_767(data, 4, 8)    # -> cross-byte extraction
            extract_bits_767(data, 8, 16)   # -> 0x3456 (two bytes)
        """
        return extract_bits(data, start_bit, length, signed)

    def compute_absolute_bit_start(
        self, words_per_subframe: int, word_bits: int
    ) -> int:
        """Compute MSB-indexed bit start for ARINC 717 frames.

        Calculates absolute bit position from subframe, word, and bit_offset fields.
        Used by ARINC 717 decoder when parameters are defined in word-based format.

        Args:
            words_per_subframe: number of words per subframe (typically 4)
            word_bits: bits per word (typically 12)

        Returns:
            Absolute bit position (0-based MSB-first)

        Formula:
            bit_start = subframe * (words_per_subframe * word_bits)
                      + word * word_bits
                      + bit_offset
        """
        subframe_bits = words_per_subframe * word_bits
        return self.subframe * subframe_bits + self.word * word_bits + self.bit_offset

    def decode_from_frame(
        self, frame_bytes: bytes, words_per_subframe: int, word_bits: int
    ) -> tuple[Any, bool]:
        """Decode this parameter from a full frame bytes buffer (ARINC 717 style).

        Used by Arinc717Decoder. Supports both absolute start_bit indexing and
        word-based indexing (subframe/word/bit_offset).

        Args:
            frame_bytes: complete frame bytes buffer
            words_per_subframe: words per subframe (typically 4)
            word_bits: bits per word (typically 12)

        Returns:
            (decoded_value, is_valid) tuple where is_valid=False if out of bounds
        """
        # Prefer explicit start_bit if set, otherwise compute from word fields
        if self.start_bit is not None:
            start = self.start_bit
        else:
            start = self.compute_absolute_bit_start(words_per_subframe, word_bits)

        total_bits = len(frame_bytes) * 8
        if start < 0 or (start + self.bit_length) > total_bits:
            logger.debug(
                f"Parameter {self.name}: out of bounds (start={start}, length={self.bit_length}, total={total_bits})"
            )
            return (None, False)

        raw = extract_bits(frame_bytes, start, self.bit_length, signed=self.signed)
        decoded = self.decode(raw)
        return (decoded, True)

    def decode(self, raw_bits: int) -> Any:
        """Decode raw integer bits according to ARINC data_type.

        Dispatches to type-specific decoders based on self.data_type.
        Supports all ARINC 767 types: BNR, BCD, DISCRETE, CHAR, UTC, PACKED, COB.

        Args:
            raw_bits: extracted integer bit value

        Returns:
            Decoded value (type depends on data_type)
        """
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

        # Fallback: return raw value
        logger.warning(
            f"Parameter {self.name}: unknown data_type '{self.data_type}', returning raw value"
        )
        return raw_bits

    def _decode_bnr(self, raw_bits: int) -> float:
        """Decode Binary Number (BNR) format.

        Notes:
            - Signed interpretation is handled by extract_bits(), so `raw_bits`
            is already a correctly signed integer when this method is called.
            - This method applies only scale and offset transformations.
            - If no scale or offset is provided, the raw integer value is returned
            as a float.

        BNR calculation:
            value = raw_bits
            if scale is provided:  value *= scale
            if offset is provided: value += offset

        Returns:
            float: scaled and offset-adjusted numeric value.
        """
        val = float(raw_bits)
        if self.scale is not None:
            val *= self.scale
        if self.offset is not None:
            val += self.offset
        return val

    def _decode_discrete(self, raw_bits: int) -> Any:
        """Decode DISCRETE format.

        DISCRETE is either a single-bit boolean or multi-bit integer.

        Returns:
            bool if bit_length==1, else int
        """
        if self.bit_length == 1:
            return bool(raw_bits)
        return int(raw_bits)

    def _decode_bcd(self, raw_bits: int) -> str:
        """Decode Binary-Coded Decimal (BCD) format.

        BCD packs decimal digits into 4-bit nibbles.
        Example: 0x123 represents decimal 123 (digits 1, 2, 3).

        Returns:
            str decimal representation
        """
        if raw_bits == 0:
            return "0"
        digits = []
        n = raw_bits
        while n > 0:
            digits.append(str(n & 0xF))
            n >>= 4
        return "".join(reversed(digits))

    def _decode_char(self, raw_bits: int) -> str:
        """Decode CHARACTER/ASCII format.

        Packs ASCII characters into byte boundaries.

        Returns:
            str with ASCII characters, trailing nulls stripped
        """
        byte_len = (self.bit_length + 7) // 8
        b = int(raw_bits).to_bytes(byte_len, "big")
        return b.rstrip(b"\x00").decode("ascii", errors="replace")

    def _decode_utc(self, raw_bits: int) -> str:
        """Decode UTC time format.

        UTC is typically encoded as BCD HH:MM:SS (6 decimal digits) packed
        directly into nibbles, e.g. 23:59:59 -> raw_bits == 0x235959.

        Returns:
            str in format "HH:MM:SS"
        """
        s = self._decode_bcd(raw_bits).rjust(6, "0")
        hh = int(s[0:2])
        mm = int(s[2:4])
        ss = int(s[4:6])
        return f"{hh:02d}:{mm:02d}:{ss:02d}"

    def _decode_cob(self, raw_bits: int) -> Any:
        """Decode Computed On Board (COB) parameter.

        COB parameters may reference a formula for computation.
        If cob_formula is provided, it is evaluated with restricted namespace.
        Otherwise returns raw integer.

        Formula evaluation context:
            - "raw": the extracted bit value
            - "scale": self.scale (or 1.0 if None)
            - "offset": self.offset (or 0.0 if None)

        Example:
            cob_formula="raw * 0.00390625" -> Mach computation
            cob_formula="raw / 100.0 + offset" -> with offset

        Returns:
            Computed value (typically float) or raw int if no formula

        Safety:
            Uses restricted eval() with no __builtins__ access.
            NOTE: this is not a true sandbox -- attribute-chain sandbox
            escapes are possible in plain Python eval(). Do not load
            cob_formula values from untrusted sources without further
            hardening (e.g. an AST allowlist).
        """
        if self.cob_formula:
            ctx = {
                "raw": raw_bits,
                "scale": self.scale or 1.0,
                "offset": self.offset or 0.0,
            }
            try:
                result = eval(self.cob_formula, {"__builtins__": {}}, ctx)
                logger.debug(f"Parameter {self.name}: COB formula evaluated: {result}")
                return result
            except Exception as e:
                logger.warning(
                    f"Parameter {self.name}: COB formula evaluation failed: {e}, returning raw value"
                )
                return raw_bits

        return raw_bits

    @staticmethod
    def _bcd_from_int(value: int) -> int:
        """Convert integer to Binary-Coded Decimal representation.

        Example:
            123 (decimal) -> 0x123 (BCD)

        Args:
            value: integer to convert

        Returns:
            BCD encoded integer
        """
        out = 0
        multiplier = 1
        v = value
        while v > 0:
            digit = v & 0xF
            out = digit * multiplier + out
            multiplier *= 10
            v >>= 4
        return out
