from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BitstreamScanner:
    """Find sync word positions in a raw bitstream.

    This scanner is configurable with a sync pattern (provided as an integer)
    and a sync length in bits. It scans the bitstream (MSB-first) and returns
    a list of bit offsets where the sync matches exactly.
    """

    def __init__(self, sync_pattern: int, sync_length: int = 16) -> None:
        self.sync_pattern = sync_pattern
        self.sync_length = sync_length

    def find_sync_positions(self, data: bytes) -> list[int]:
        """Return list of bit offsets where the sync pattern occurs using direct byte windowing."""
        positions: list[int] = []
        total_bits = len(data) * 8
        if self.sync_length <= 0 or self.sync_length > total_bits:
            return positions

        mask = (1 << self.sync_length) - 1
        window = 0

        # Preload the sliding window bit by bit
        for bit_idx in range(self.sync_length - 1):
            byte_pos = bit_idx >> 3
            bit_shift = 7 - (bit_idx & 7)
            bit = (data[byte_pos] >> bit_shift) & 1
            window = (window << 1) | bit

        # Scan through the rest of the stream
        for bit_idx in range(self.sync_length - 1, total_bits):
            byte_pos = bit_idx >> 3
            bit_shift = 7 - (bit_idx & 7)
            bit = (data[byte_pos] >> bit_shift) & 1

            window = ((window << 1) & mask) | bit

            if window == self.sync_pattern:
                pos = bit_idx - (self.sync_length - 1)
                positions.append(pos)

        logger.debug("Found %d sync positions", len(positions))
        return positions
