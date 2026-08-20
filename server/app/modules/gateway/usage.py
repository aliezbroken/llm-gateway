"""Parse token usage from upstream responses (both JSON and SSE streaming)."""

import json
import re
from typing import Optional

_SSE_DATA = re.compile(r"^data:\s?(.*)$")

USAGE_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def parse_usage_from_json(body: bytes) -> dict | None:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    usage = data.get("usage")
    if isinstance(usage, dict):
        return usage
    return None


def collect_usage_from_sse(chunks: list[bytes]) -> dict | None:
    """Scan buffered SSE chunks, return the usage from the final chunk if present.

    vLLM streams `data: {...}` events and a final `data: [DONE]`; when
    `stream_options.include_usage=true` the second-to-last event carries usage.
    We look for the last event object that contains a `usage` field.
    """
    last_usage: dict | None = None
    for chunk in chunks:
        text = chunk.decode("utf-8", errors="replace")
        for line in text.splitlines():
            m = _SSE_DATA.match(line)
            if not m:
                continue
            payload = m.group(1).strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            u = obj.get("usage")
            if isinstance(u, dict):
                last_usage = u
    return last_usage


def pick(usage: dict | None, field: str, default: int = 0) -> int:
    if not usage:
        return default
    val = usage.get(field)
    return val if isinstance(val, int) else default


class SSEUsageTracker:
    """Incrementally scan a streaming body for `usage` without buffering it all.

    Keeps only the previous and current complete SSE `data:` payloads, which is
    enough because vLLM sends usage in the event right before [DONE].
    """

    def __init__(self) -> None:
        self._pending = ""
        self._last: str | None = None
        self._prev: str | None = None

    def feed(self, chunk: bytes) -> None:
        self._pending += chunk.decode("utf-8", errors="replace")
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            m = _SSE_DATA.match(line)
            if not m:
                continue
            payload = m.group(1).strip()
            if not payload or payload == "[DONE]":
                continue
            self._prev, self._last = self._last, payload

    def usage(self) -> dict | None:
        for payload in (self._last, self._prev):
            if not payload:
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            u = obj.get("usage")
            if isinstance(u, dict):
                return u
        return None
