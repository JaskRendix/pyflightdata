from __future__ import annotations

import logging
from collections.abc import Iterable

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
        """Return list of bit offsets where the sync pattern occurs.

        This is a deterministic, exact-match scanner. It can be extended to
        handle fuzzy matches or bit slips.
        """
        bits = list(self._bits_from_bytes(data))
        positions: list[int] = []
        total = len(bits)
        if self.sync_length <= 0 or self.sync_length > total:
            return positions
        # build integer window
        mask = (1 << self.sync_length) - 1
        window = 0
        # preload first sync_length-1 bits
        for i in range(self.sync_length - 1):
            window = (window << 1) | bits[i]
        for i in range(self.sync_length - 1, total):
            window = ((window << 1) & mask) | bits[i]
            # compute pattern as integer
            if window == self.sync_pattern:
                pos = i - (self.sync_length - 1)
                positions.append(pos)
        logger.debug("Found %d sync positions", len(positions))
        return positions

    @staticmethod
    def _bits_from_bytes(data: bytes) -> Iterable[int]:
        for b in data:
            for i in range(7, -1, -1):
                yield (b >> i) & 1
