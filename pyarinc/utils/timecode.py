from datetime import datetime, timezone


def utc_from_components(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0
) -> datetime:
    """Create a timezone-aware UTC datetime from components."""
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def parse_utc_string(s: str) -> datetime | None:
    """Parse a few common UTC string formats to datetime, returns None if unknown."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None
