from dataclasses import dataclass
from typing import Any


@dataclass
class SourceMeta:
    sample_rate: int
    provider: str
    extra: dict[str, Any]
