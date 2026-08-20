from datetime import datetime, timezone
from pathlib import Path


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
