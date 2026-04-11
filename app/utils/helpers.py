from datetime import datetime, timezone
from uuid import uuid4


def utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def generate_reference(prefix: str, length: int = 8) -> str:
    timestamp = utcnow().strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:length].upper()
    return f"{prefix}-{timestamp}-{suffix}"
