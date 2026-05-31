from pathlib import Path


def read_binary(path: str | Path) -> bytes:
    """Read a binary datafile and return bytes.

    This is a simple, safe reader with no side effects.
    """
    p = Path(path)
    return p.read_bytes()
