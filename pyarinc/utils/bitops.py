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
    """Extract exactly `length` bits starting at `start` (0-based MSB indexing)."""

    if length <= 0:
        return 0

    total_bits = len(data) * 8

    # Strict bounds
    if start < 0 or (start + length) > total_bits:
        raise ValueError(
            f"extract_bits: out of bounds (start={start}, length={length}, total={total_bits})"
        )

    # Convert to big integer
    big = int.from_bytes(data, "big")

    # Compute shift from MSB
    shift = total_bits - (start + length)

    # Mask for exactly `length` bits
    mask = (1 << length) - 1

    value = (big >> shift) & mask

    # Signed two's complement
    if signed:
        sign_bit = 1 << (length - 1)
        if value & sign_bit:
            value -= 1 << length

    return value
