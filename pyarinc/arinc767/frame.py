from __future__ import annotations

import logging
import struct
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Arinc767Frame:
    """Represents a single ARINC 767 frame."""

    raw_bytes: bytes
    frame_index: int
    frame_id: int
    frame_type: int
    timestamp_ms: int  # milliseconds since start

    @property
    def data(self) -> bytes:
        """Return the data section (between header and trailer)."""
        return self.raw_bytes[10:-2]  # skip 10-byte header, 2-byte trailer

    @property
    def timestamp_str(self) -> str:
        """Return formatted timestamp HH:MM:SS.MSS."""
        total_secs = self.timestamp_ms // 1000
        ms = self.timestamp_ms % 1000
        secs = total_secs % 60
        mins = (total_secs // 60) % 60
        hours = (total_secs // 3600) % 24
        return f"{hours:02d}:{mins:02d}:{secs:02d}.{ms:03d}"


class Arinc767FrameParser:
    """Parse ARINC 767 frames from a byte stream."""

    SYNC_WORD = 0xEB90
    HEADER_SIZE = 10
    TRAILER_SIZE = 2

    @staticmethod
    def find_sync_positions(data: bytes) -> list[int]:
        """Find all sync word positions in the data."""
        positions = []
        for i in range(len(data) - 1):
            word = struct.unpack(">H", data[i : i + 2])[0]
            if word == Arinc767FrameParser.SYNC_WORD:
                positions.append(i)
        return positions

    @staticmethod
    def parse_frame(
        data: bytes, frame_start: int, frame_index: int
    ) -> Arinc767Frame | None:
        """Parse a single frame starting at frame_start byte offset.

        Returns Arinc767Frame if valid, None otherwise.
        """
        if frame_start + Arinc767FrameParser.HEADER_SIZE > len(data):
            return None

        # Read header
        sync = struct.unpack(">H", data[frame_start : frame_start + 2])[0]
        if sync != Arinc767FrameParser.SYNC_WORD:
            return None

        frame_len = struct.unpack(">H", data[frame_start + 2 : frame_start + 4])[0]
        timestamp_ms = struct.unpack(">I", data[frame_start + 4 : frame_start + 8])[0]
        frame_type_id = struct.unpack(">H", data[frame_start + 8 : frame_start + 10])[0]
        frame_type = (frame_type_id >> 8) & 0xFF
        frame_id = frame_type_id & 0xFF

        # Validate frame length
        if (
            frame_len
            < Arinc767FrameParser.HEADER_SIZE + Arinc767FrameParser.TRAILER_SIZE
        ):
            return None
        if frame_start + frame_len > len(data):
            return None

        # Extract raw frame bytes
        frame_bytes = data[frame_start : frame_start + frame_len]

        # Validate trailer
        trailer_type_id = struct.unpack(">H", frame_bytes[-2:])[0]
        trailer_type = (trailer_type_id >> 8) & 0xFF
        trailer_id = trailer_type_id & 0xFF
        if trailer_type != frame_type or trailer_id != frame_id:
            logger.warning(f"Frame {frame_index}: header/trailer mismatch")
            # Don't fail, just log

        if frame_type != 0:
            logger.debug(f"Frame {frame_index}: non-standard frame type {frame_type}")

        return Arinc767Frame(
            raw_bytes=frame_bytes,
            frame_index=frame_index,
            frame_id=frame_id,
            frame_type=frame_type,
            timestamp_ms=timestamp_ms,
        )

    @staticmethod
    def parse_frames(data: bytes) -> list[Arinc767Frame]:
        """Parse all valid ARINC 767 frames from data."""
        frames = []
        positions = Arinc767FrameParser.find_sync_positions(data)
        if not positions:
            return frames

        for idx, pos in enumerate(positions):
            frame = Arinc767FrameParser.parse_frame(data, pos, idx)
            if frame is not None:
                frames.append(frame)

        return frames
