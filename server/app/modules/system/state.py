from datetime import datetime, timezone

online: bool = False
latency_ms: float = 0.0
last_check: datetime | None = None
message: str = ""

_UPSTREAM_OVERRIDE: str | None = None


def get_upstream_override() -> str | None:
    return _UPSTREAM_OVERRIDE


def set_upstream_override(url: str | None) -> None:
    global _UPSTREAM_OVERRIDE
    _UPSTREAM_OVERRIDE = url


def snapshot() -> dict:
    return {
        "online": online,
        "latency_ms": latency_ms,
        "last_check": last_check,
        "message": message,
    }
