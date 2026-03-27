from datetime import datetime
from uuid import uuid4


def generate_reference(prefix: str, length: int = 8) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:length].upper()
    return f"{prefix}-{timestamp}-{suffix}"
