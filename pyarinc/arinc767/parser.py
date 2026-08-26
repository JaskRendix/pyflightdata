from __future__ import annotations

import logging
import struct
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .frame import Arinc767Frame

logger = logging.getLogger(__name__)

_STRUCT_U16 = struct.Struct(">H")
_STRUCT_U32 = struct.Struct(">I")


@dataclass
class Arinc767ParseResult:
    """Diagnostic container for parsing statistics and frames."""

    frames: list[Arinc767Frame] = field(default_factory=list)
    total_bytes_processed: int = 0
    valid_frames_count: int = 0
    gaps_encountered: int = 0
    total_gap_bytes: int = 0
    trailer_mismatches: int = 0
    embedded_headers_detected: int = 0


class Arinc767FrameParser:
    """Parse ARINC 767 frames from raw byte streams or massive files with telemetry diagnostics."""

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
        """Find all sync word positions in data (first pass)."""
        positions = []
        for i in range(len(data) - 1):
            word = _STRUCT_U16.unpack(data[i : i + 2])[0]
            if word == Arinc767FrameParser.SYNC_WORD:
                positions.append(i)
        return positions

    @staticmethod
    def _looks_like_frame_start(data: bytes, pos: int) -> bool:
        """Check whether `pos` is a plausible frame start."""
        if pos + Arinc767FrameParser.HEADER_SIZE > len(data):
            return False
        try:
            word = _STRUCT_U16.unpack(data[pos : pos + 2])[0]
        except struct.error:
            return False
        if word != Arinc767FrameParser.SYNC_WORD:
            return False
        try:
            frame_len = _STRUCT_U16.unpack(data[pos + 2 : pos + 4])[0]
        except struct.error:
            return False
        if (
            frame_len < Arinc767FrameParser.MIN_FRAME_SIZE
            or frame_len > Arinc767FrameParser.MAX_FRAME_SIZE
        ):
            return False
        if pos + frame_len > len(data):
            return False
        return True

    @staticmethod
    def find_valid_frame_start(data: bytes, start_pos: int) -> tuple[int, int] | None:
        """Find next valid frame starting at or after start_pos."""
        for pos in range(start_pos, len(data) - Arinc767FrameParser.HEADER_SIZE):
            word = _STRUCT_U16.unpack(data[pos : pos + 2])[0]
            if word != Arinc767FrameParser.SYNC_WORD:
                continue

            try:
                frame_len = _STRUCT_U16.unpack(data[pos + 2 : pos + 4])[0]
            except struct.error:
                continue

            if (
                frame_len < Arinc767FrameParser.MIN_FRAME_SIZE
                or frame_len > Arinc767FrameParser.MAX_FRAME_SIZE
            ):
                continue

            if pos + frame_len > len(data):
                continue

            return (pos, frame_len)

        return None

    @staticmethod
    def parse_frame(
        data: bytes, frame_start: int, frame_index: int, strict: bool = False
    ) -> tuple[Arinc767Frame | None, bool]:
        """Parse a single frame starting at frame_start byte offset.

        Returns:
            Tuple of (Arinc767Frame or None, trailer_mismatch_occurred_bool)
        """
        if frame_start + Arinc767FrameParser.HEADER_SIZE > len(data):
            logger.debug(
                f"Frame {frame_index}: not enough data for header at offset {frame_start:#x}"
            )
            return None, False

        try:
            sync = _STRUCT_U16.unpack(data[frame_start : frame_start + 2])[0]
        except struct.error:
            logger.debug(
                f"Frame {frame_index}: failed to read sync at offset {frame_start:#x}"
            )
            return None, False

        if sync != Arinc767FrameParser.SYNC_WORD:
            logger.debug(
                f"Frame {frame_index}: sync mismatch (expected 0x{Arinc767FrameParser.SYNC_WORD:04x}, got 0x{sync:04x})"
            )
            return None, False

        try:
            frame_len = _STRUCT_U16.unpack(data[frame_start + 2 : frame_start + 4])[0]
        except struct.error:
            logger.debug(
                f"Frame {frame_index}: failed to read frame length at offset {frame_start:#x}"
            )
            return None, False

        if (
            frame_len < Arinc767FrameParser.MIN_FRAME_SIZE
            or frame_len > Arinc767FrameParser.MAX_FRAME_SIZE
        ):
            logger.debug(
                f"Frame {frame_index}: invalid length {frame_len} (expected 14-2048) at offset {frame_start:#x}"
            )
            return None, False

        if strict and frame_len != (
            Arinc767FrameParser.HEADER_SIZE
            + Arinc767FrameParser.TRAILER_SIZE
            + len(data[frame_start + 10 : frame_start + frame_len - 2])
        ):
            logger.debug(
                f"Frame {frame_index}: strict length match failure at offset {frame_start:#x}"
            )
            return None, False

        if frame_start + frame_len > len(data):
            logger.debug(
                f"Frame {frame_index}: frame extends beyond buffer "
                f"(start={frame_start:#x}, len={frame_len}, buf_len={len(data)})"
            )
            return None, False

        try:
            timestamp_ms = _STRUCT_U32.unpack(data[frame_start + 4 : frame_start + 8])[
                0
            ]
        except struct.error:
            logger.debug(
                f"Frame {frame_index}: failed to read timestamp at offset {frame_start:#x}"
            )
            return None, False

        try:
            frame_type_id = _STRUCT_U16.unpack(
                data[frame_start + 8 : frame_start + 10]
            )[0]
        except struct.error:
            logger.debug(
                f"Frame {frame_index}: failed to read frame type/id at offset {frame_start:#x}"
            )
            return None, False

        frame_type = (frame_type_id >> 8) & 0xFF
        frame_id = frame_type_id & 0xFF

        frame_bytes = data[frame_start : frame_start + frame_len]

        frame = Arinc767Frame(
            raw_bytes=frame_bytes,
            frame_index=frame_index,
            frame_id=frame_id,
            frame_type=frame_type,
            timestamp_ms=timestamp_ms,
        )

        if not frame.is_valid():
            logger.debug(
                f"Frame {frame_index}: frame too small at offset {frame_start:#x}"
            )
            return None, False

        trailer_mismatch = False
        if not frame.validate_trailer():
            trailer_mismatch = True
            if strict:
                logger.debug(
                    f"Frame {frame_index}: trailer mismatch (strict mode) at offset {frame_start:#x}"
                )
                return None, True
            logger.warning(
                f"Frame {frame_index}: trailer type/id mismatch "
                f"(header: type=0x{frame_type:02x}, id=0x{frame_id:02x}) at offset {frame_start:#x}"
            )

        logger.debug(
            f"Frame {frame_index}: parsed successfully at offset {frame_start:#x} (len={frame_len})"
        )
        return frame, trailer_mismatch

    @staticmethod
    def iter_frames(
        data: bytes,
        strict: bool = False,
        timestamp_wrap: bool = False,
        max_gap: int | None = None,
        max_frames: int = 500000,
    ) -> Iterable[Arinc767Frame]:
        """Iterate over all valid frames in a byte buffer."""
        # Fast path check for sync word presence
        if b"\xEB\x90" not in data:
            logger.debug("No ARINC 767 sync word (0xEB90) found in data stream.")
            return

        pos = 0
        frame_index = 0
        last_gap_pos = None
        last_timestamp = None
        cumulative_offset = 0

        while pos < len(data) and frame_index < max_frames:
            result = Arinc767FrameParser.find_valid_frame_start(data, pos)
            if result is None:
                break

            frame_start, frame_len = result

            if frame_start > pos:
                gap_size = frame_start - pos
                if strict:
                    return
                if max_gap is not None and gap_size > max_gap:
                    logger.warning(
                        f"Large gap detected: {gap_size} bytes exceeds max_gap threshold ({max_gap}) at {frame_start:#x}"
                    )
                if frame_start != last_gap_pos:
                    logger.warning(
                        f"Frame {frame_index}: gap of {gap_size} bytes before frame at offset {frame_start:#x}"
                    )
                    last_gap_pos = frame_start

            inner_sync = None
            end_search = min(frame_start + frame_len, len(data) - 1)
            for i in range(frame_start + 1, end_search):
                if Arinc767FrameParser._looks_like_frame_start(data, i):
                    inner_sync = i
                    break

            if inner_sync is not None:
                logger.warning(
                    f"Frame {frame_index}: embedded frame header detected at "
                    f"{inner_sync:#x} inside frame starting at {frame_start:#x}; "
                    f"resuming parse from inner frame"
                )
                pos = inner_sync
                continue

            frame, _ = Arinc767FrameParser.parse_frame(
                data, frame_start, frame_index, strict=strict
            )
            if frame is not None:
                ts = frame.timestamp_ms
                if timestamp_wrap:
                    if last_timestamp is not None and ts < last_timestamp:
                        cumulative_offset += 24 * 3600 * 1000
                    ts_adj = ts + cumulative_offset
                    frame.timestamp_ms = ts_adj
                    last_timestamp = ts_adj
                else:
                    if last_timestamp is not None and ts < last_timestamp:
                        logger.warning(
                            f"Frame {frame_index}: timestamp regression detected ({ts} < {last_timestamp})"
                        )
                    last_timestamp = ts

                yield frame
                frame_index += 1

            pos = frame_start + frame_len

    @staticmethod
    def parse_with_stats(
        data: bytes,
        strict: bool = False,
        timestamp_wrap: bool = False,
        max_gap: int | None = None,
        max_frames: int = 500000,
    ) -> Arinc767ParseResult:
        """Parse frames from buffer and compile complete diagnostic statistics."""
        stats = Arinc767ParseResult(total_bytes_processed=len(data))
        if b"\xEB\x90" not in data:
            return stats

        pos = 0
        frame_index = 0
        last_gap_pos = None
        last_timestamp = None
        cumulative_offset = 0

        while pos < len(data) and frame_index < max_frames:
            result = Arinc767FrameParser.find_valid_frame_start(data, pos)
            if result is None:
                break

            frame_start, frame_len = result

            if frame_start > pos:
                gap_size = frame_start - pos
                if strict:
                    break
                stats.gaps_encountered += 1
                stats.total_gap_bytes += gap_size
                if max_gap is not None and gap_size > max_gap:
                    logger.warning(
                        f"Large gap detected: {gap_size} bytes exceeds max_gap threshold ({max_gap}) at {frame_start:#x}"
                    )
                if frame_start != last_gap_pos:
                    logger.warning(
                        f"Frame {frame_index}: gap of {gap_size} bytes before frame at offset {frame_start:#x}"
                    )
                    last_gap_pos = frame_start

            inner_sync = None
            end_search = min(frame_start + frame_len, len(data) - 1)
            for i in range(frame_start + 1, end_search):
                if Arinc767FrameParser._looks_like_frame_start(data, i):
                    inner_sync = i
                    break

            if inner_sync is not None:
                stats.embedded_headers_detected += 1
                logger.warning(
                    f"Frame {frame_index}: embedded frame header detected at "
                    f"{inner_sync:#x} inside frame starting at {frame_start:#x}; "
                    f"resuming parse from inner frame"
                )
                pos = inner_sync
                continue

            frame, trailer_mismatch = Arinc767FrameParser.parse_frame(
                data, frame_start, frame_index, strict=strict
            )
            if trailer_mismatch:
                stats.trailer_mismatches += 1

            if frame is not None:
                ts = frame.timestamp_ms
                if timestamp_wrap:
                    if last_timestamp is not None and ts < last_timestamp:
                        cumulative_offset += 24 * 3600 * 1000
                    ts_adj = ts + cumulative_offset
                    frame.timestamp_ms = ts_adj
                    last_timestamp = ts_adj
                else:
                    if last_timestamp is not None and ts < last_timestamp:
                        logger.warning(
                            f"Frame {frame_index}: timestamp regression detected ({ts} < {last_timestamp})"
                        )
                    last_timestamp = ts

                stats.frames.append(frame)
                stats.valid_frames_count += 1
                frame_index += 1

            pos = frame_start + frame_len

        return stats

    @staticmethod
    def iter_frames_from_file(
        file_path: str | Path,
        chunk_size: int = 1024 * 1024,
        **kwargs,
    ) -> Iterable[Arinc767Frame]:
        """Stream-parse ARINC 767 frames from a file path chunk-by-chunk to save memory."""
        path = Path(file_path)
        buffer = bytearray()
        overlap_size = 2048  # Max frame size to safely handle boundary sync splits
        frame_index = 0
        cumulative_offset = 0
        last_timestamp = None

        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                buffer.extend(chunk)

                # Process all complete frames currently in buffer
                pos = 0
                while pos < len(buffer):
                    result = Arinc767FrameParser.find_valid_frame_start(buffer, pos)
                    if result is None:
                        break

                    frame_start, frame_len = result

                    # If the valid frame requires data beyond our current buffer edge, stop and wait for next chunk
                    if frame_start + frame_len > len(buffer):
                        break

                    frame, _ = Arinc767FrameParser.parse_frame(
                        buffer,
                        frame_start,
                        frame_index,
                        strict=kwargs.get("strict", False),
                    )
                    if frame is not None:
                        ts = frame.timestamp_ms
                        if kwargs.get("timestamp_wrap", False):
                            if last_timestamp is not None and ts < last_timestamp:
                                cumulative_offset += 24 * 3600 * 1000
                            ts_adj = ts + cumulative_offset
                            frame.timestamp_ms = ts_adj
                            last_timestamp = ts_adj
                        else:
                            last_timestamp = ts

                        yield frame
                        frame_index += 1

                    pos = frame_start + frame_len

                # Retain tail bytes in buffer to handle sync boundaries across chunks
                if pos > 0:
                    del buffer[:pos]
                elif len(buffer) > chunk_size * 2:
                    # Safety valve if no frames found for a very long stretch
                    del buffer[:-overlap_size]

        # Process any remaining residual buffer bytes after EOF
        if len(buffer) >= Arinc767FrameParser.MIN_FRAME_SIZE:
            for frame in Arinc767FrameParser.iter_frames(bytes(buffer), **kwargs):
                frame.frame_index = frame_index
                yield frame
                frame_index += 1

    @staticmethod
    def parse_all(data: bytes, **kwargs) -> list[Arinc767Frame]:
        """Convenience wrapper to parse all frames into a list."""
        return list(Arinc767FrameParser.iter_frames(data, **kwargs))

    @staticmethod
    def summarize(frame: Arinc767Frame) -> str:
        """Return a compact human-readable summary of a frame for debugging."""
        return (
            f"idx={frame.frame_index}, "
            f"id=0x{frame.frame_id:02x}, "
            f"type=0x{frame.frame_type:02x}, "
            f"ts={frame.timestamp_ms}ms ({frame.timestamp_str}), "
            f"len={len(frame.raw_bytes)}"
        )
