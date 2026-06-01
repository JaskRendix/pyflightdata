from __future__ import annotations

import logging
import struct
from collections.abc import Iterable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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


class Arinc767FrameParser:
    """Parse ARINC 767 frames from raw byte stream."""

    SYNC_WORD: int = 0xEB90
    """Sync word constant: 0xEB90 (big-endian)."""

    HEADER_SIZE: int = 10
    """Frame header size: 2 (sync) + 2 (len) + 4 (timestamp) + 1 (type) + 1 (id)."""

    TRAILER_SIZE: int = 2
    """Frame trailer size: 1 (type) + 1 (id)."""

    MIN_FRAME_SIZE: int = 14
    """Minimum frame size: 10 (header) + 2 (trailer) + 2 (min data)."""

    MAX_FRAME_SIZE: int = 2048
    """Maximum frame size per ARINC 767 specification."""

    @staticmethod
    def find_sync_positions(data: bytes) -> list[int]:
        """Find all sync word positions in data (first pass).

        Args:
            data: raw byte buffer

        Returns:
            list of byte offsets where 0xEB90 is found (big-endian).

        Note:
            This is a coarse-grained search. Not all sync positions are valid
            frame starts. Use find_valid_frame_start() for validation.
        """
        positions = []
        for i in range(len(data) - 1):
            word = struct.unpack(">H", data[i : i + 2])[0]
            if word == Arinc767FrameParser.SYNC_WORD:
                positions.append(i)
        return positions

    @staticmethod
    def find_valid_frame_start(data: bytes, start_pos: int) -> tuple[int, int] | None:
        """Find next valid frame starting at or after start_pos.

        Scans forward from start_pos looking for a position where:
          1. Sync word 0xEB90 is present
          2. Frame length field is in valid range (14-2048)
          3. Frame end position is within data bounds
          4. Frame structure is minimally sound

        Args:
            data: raw byte buffer
            start_pos: byte offset to start scanning from

        Returns:
            (frame_start_pos, frame_length) tuple if valid frame found.
            None if no valid frame found before end of buffer.
        """
        for pos in range(start_pos, len(data) - Arinc767FrameParser.HEADER_SIZE):
            # Check sync word
            word = struct.unpack(">H", data[pos : pos + 2])[0]
            if word != Arinc767FrameParser.SYNC_WORD:
                continue

            # Extract frame length
            try:
                frame_len = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
            except struct.error:
                continue

            # Validate frame length range
            if (
                frame_len < Arinc767FrameParser.MIN_FRAME_SIZE
                or frame_len > Arinc767FrameParser.MAX_FRAME_SIZE
            ):
                continue

            # Verify frame fits in buffer
            if pos + frame_len > len(data):
                continue

            # Found a potential valid frame start
            return (pos, frame_len)

        return None

    @staticmethod
    def parse_frame(
        data: bytes, frame_start: int, frame_index: int
    ) -> Arinc767Frame | None:
        """Parse a single frame starting at frame_start byte offset.

        Extracts and validates all frame metadata (header, timestamp, type, id).
        Checks that trailer type/id match header.

        Args:
            data: raw byte buffer
            frame_start: byte offset to frame start (should be at sync word)
            frame_index: sequential frame number in stream (for logging)

        Returns:
            Arinc767Frame if valid and well-formed, None if malformed.
        """
        # Verify minimum space for header
        if frame_start + Arinc767FrameParser.HEADER_SIZE > len(data):
            logger.debug(
                f"Frame {frame_index}: not enough data for header at offset {frame_start:#x}"
            )
            return None

        # Read and verify sync word
        try:
            sync = struct.unpack(">H", data[frame_start : frame_start + 2])[0]
        except struct.error:
            logger.debug(
                f"Frame {frame_index}: failed to read sync at offset {frame_start:#x}"
            )
            return None

        if sync != Arinc767FrameParser.SYNC_WORD:
            logger.debug(
                f"Frame {frame_index}: sync mismatch (expected 0x{Arinc767FrameParser.SYNC_WORD:04x}, got 0x{sync:04x})"
            )
            return None

        # Read frame length
        try:
            frame_len = struct.unpack(">H", data[frame_start + 2 : frame_start + 4])[0]
        except struct.error:
            logger.debug(
                f"Frame {frame_index}: failed to read frame length at offset {frame_start:#x}"
            )
            return None

        # Validate frame length
        if (
            frame_len < Arinc767FrameParser.MIN_FRAME_SIZE
            or frame_len > Arinc767FrameParser.MAX_FRAME_SIZE
        ):
            logger.debug(
                f"Frame {frame_index}: invalid length {frame_len} (expected 14-2048) at offset {frame_start:#x}"
            )
            return None

        # Verify frame fits in buffer
        if frame_start + frame_len > len(data):
            logger.debug(
                f"Frame {frame_index}: frame extends beyond buffer "
                f"(start={frame_start:#x}, len={frame_len}, buf_len={len(data)})"
            )
            return None

        # Extract timestamp (4 bytes, big-endian)
        try:
            timestamp_ms = struct.unpack(">I", data[frame_start + 4 : frame_start + 8])[
                0
            ]
        except struct.error:
            logger.debug(
                f"Frame {frame_index}: failed to read timestamp at offset {frame_start:#x}"
            )
            return None

        # Extract frame type and ID (combined in 1 16-bit word)
        try:
            frame_type_id = struct.unpack(
                ">H", data[frame_start + 8 : frame_start + 10]
            )[0]
        except struct.error:
            logger.debug(
                f"Frame {frame_index}: failed to read frame type/id at offset {frame_start:#x}"
            )
            return None

        frame_type = (frame_type_id >> 8) & 0xFF
        frame_id = frame_type_id & 0xFF

        # Extract raw frame bytes
        frame_bytes = data[frame_start : frame_start + frame_len]

        # Create frame object
        frame = Arinc767Frame(
            raw_bytes=frame_bytes,
            frame_index=frame_index,
            frame_id=frame_id,
            frame_type=frame_type,
            timestamp_ms=timestamp_ms,
        )

        # Validate frame structure
        if not frame.is_valid():
            logger.debug(
                f"Frame {frame_index}: frame too small at offset {frame_start:#x}"
            )
            return None

        # Validate trailer (warn but don't fail)
        if not frame.validate_trailer():
            logger.warning(
                f"Frame {frame_index}: trailer type/id mismatch "
                f"(header: type=0x{frame_type:02x}, id=0x{frame_id:02x}) at offset {frame_start:#x}"
            )

        logger.debug(
            f"Frame {frame_index}: parsed successfully at offset {frame_start:#x} (len={frame_len})"
        )
        return frame

    @staticmethod
    def iter_frames(data: bytes) -> Iterable[Arinc767Frame]:
        """Iterate over all valid frames in a byte buffer.

        Scans from start to end, finds frame boundaries, validates structure,
        and yields Arinc767Frame objects in order. Logs warnings for malformed
        frames but continues parsing to find subsequent frames.

        Args:
            data: raw byte buffer containing one or more ARINC 767 frames

        Yields:
            Arinc767Frame objects in order of appearance in buffer
        """
        pos = 0
        frame_index = 0
        gap_logged = False

        while pos < len(data):
            # Find next valid frame start
            result = Arinc767FrameParser.find_valid_frame_start(data, pos)
            if result is None:
                # No more valid frames
                if pos < len(data) and not gap_logged:
                    remaining = len(data) - pos
                    logger.debug(
                        f"End of frame stream: {remaining} bytes remaining at offset {pos:#x}"
                    )
                    gap_logged = True
                break

            frame_start, frame_len = result

            # Log gap if frame doesn't start immediately after last position
            if frame_start > pos and not gap_logged:
                gap_size = frame_start - pos
                logger.warning(
                    f"Frame {frame_index}: gap of {gap_size} bytes before frame at offset {frame_start:#x}"
                )

            # Parse frame at this position
            frame = Arinc767FrameParser.parse_frame(data, frame_start, frame_index)
            if frame is not None:
                yield frame
                frame_index += 1

            # Move to position after this frame
            pos = frame_start + frame_len
