from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class Arinc767Frame:
    """Represents a single ARINC 767 frame."""

    raw_bytes: bytes
    """Complete frame bytes including header, data, and trailer."""

    frame_index: int
    """Sequential frame number in the stream."""

    frame_id: int
    """Frame ID from header (0-255), identifies parameter set."""

    frame_type: int
    """Frame type from header (typically 0x00 for uncompressed fixed frames)."""

    timestamp_ms: int
    """Timestamp from header: milliseconds since start of recording."""

    @property
    def data(self) -> bytes:
        """Extract data section (bytes 10 to len-2).

        Excludes 10-byte header and 2-byte trailer.
        """
        if len(self.raw_bytes) < 12:
            return b""
        return self.raw_bytes[10:-2]

    @property
    def timestamp_str(self) -> str:
        """Return formatted timestamp HH:MM:SS.mmm."""
        ms = self.timestamp_ms % 1000
        total_secs = self.timestamp_ms // 1000
        ss = total_secs % 60
        mm = (total_secs // 60) % 60
        hh = (total_secs // 3600) % 24
        return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"

    def is_valid(self) -> bool:
        """Check if frame has minimum valid size (header + trailer + data)."""
        return len(self.raw_bytes) >= 14

    def validate_trailer(self) -> bool:
        """Verify trailer type/id match header type/id.

        Returns True if trailer matches header, False otherwise.
        """
        if len(self.raw_bytes) < 12:
            return False
        trailer_word = struct.unpack(">H", self.raw_bytes[-2:])[0]
        trailer_type = (trailer_word >> 8) & 0xFF
        trailer_id = trailer_word & 0xFF
        return trailer_type == self.frame_type and trailer_id == self.frame_id
