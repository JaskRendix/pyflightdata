from collections.abc import Iterable


def bits_from_bytes(data: bytes) -> Iterable[int]:
    """Yield bits (0/1) from big-endian bytes MSB first."""
    for b in data:
        for i in range(7, -1, -1):
            yield (b >> i) & 1


def int_from_bits(bits: Iterable[int]) -> int:
    """Convert iterable of bits (MSB first) to integer."""
    val = 0
    for bit in bits:
        val = (val << 1) | (1 if bit else 0)
    return val


def extract_bits(data: bytes, start: int, length: int, signed: bool = False) -> int:
    """Extract `length` bits starting at `start` (0-based MSB indexing) and return integer.

    Args:
        data: source bytes (MSB-first ordering)
        start: bit index (0 is the MSB of data[0])
        length: number of bits to extract
        signed: interpret result as two's complement signed integer

    Returns:
        integer value (signed if requested)
    """
    if length <= 0:
        return 0
    bits = list(bits_from_bytes(data))
    if start < 0 or start >= len(bits):
        return 0
    end = min(start + length, len(bits))
    slice_bits = bits[start:end]
    val = int_from_bits(slice_bits)
    if signed:
        # sign bit is MSB of the slice
        sign_bit = 1 << (len(slice_bits) - 1)
        if val & sign_bit:
            # two's complement negative
            val = val - (1 << len(slice_bits))
    return val
