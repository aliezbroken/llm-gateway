import asyncio
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from ...models import SystemSetting
from . import state


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(SystemSetting, key)
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(SystemSetting, key)
    if row is None:
        db.add(SystemSetting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def get_upstream_url(db: Session, default_url: str) -> str:
    return get_setting(db, "upstream_url", default_url)


def get_model_ratios(db: Session) -> dict[str, dict[str, float]]:
    raw = get_setting(db, "model_ratios", "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


async def do_health_check(upstream_url: str) -> None:
    started = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{upstream_url.rstrip('/')}/health")
        latency_ms = round((asyncio.get_event_loop().time() - started) * 1000, 2)
        state.last_check = datetime.now(timezone.utc)
        state.online = resp.status_code == 200
        state.latency_ms = latency_ms
        state.message = f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        state.last_check = datetime.now(timezone.utc)
        state.online = False
        state.latency_ms = 0.0
        state.message = str(exc)[:200]


async def health_loop(interval: int, upstream_url_provider):
    while True:
        try:
            await do_health_check(upstream_url_provider())
        except Exception:
            pass
        await asyncio.sleep(interval)
