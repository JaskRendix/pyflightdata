from typing import Any


def load_vec_config(obj: dict[str, Any]) -> dict[str, Any]:
    """Normalize a parsed VEC object into decoder-friendly structure."""
    # identity in minimal implementation
    return obj
