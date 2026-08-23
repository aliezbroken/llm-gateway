"""Test harness: real gateway app + mock upstream, both over loopback HTTP.

The gateway under test runs as a live uvicorn server in a daemon thread against a
throwaway SQLite DB, so tests exercise the full request lifecycle (auth -> limits
-> forward -> usage -> billing -> logs), including streaming.
"""

import asyncio
import json
import os
import socket
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


UPSTREAM_PORT = _free_port()
GATEWAY_PORT = _free_port()
GATEWAY_URL = f"http://127.0.0.1:{GATEWAY_PORT}"

# Env must be set before importing the app (Settings/engine are built at import time).
os.environ["UPSTREAM_URL"] = f"http://127.0.0.1:{UPSTREAM_PORT}"
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp()) / 'test.db'}"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-0123456789"  # avoid ensure_strong_jwt_secret() writing server/.env

# Usage returned by the mock upstream for every request: cost = 20 at ratio 1.0.
MOCK_USAGE = {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
REQUEST_COST = MOCK_USAGE["prompt_tokens"] + MOCK_USAGE["completion_tokens"]


# ---- mock OpenAI-compatible upstream -------------------------------------

mock_upstream = FastAPI()


@mock_upstream.get("/health")
def health():
    return {"status": "ok"}


@mock_upstream.post("/v1/chat/completions")
async def chat_completions(req: Request):
    """Extra body field `mock_delay` (seconds) slows the stream mid-flight."""
    body = await req.json()
    delay = float(body.get("mock_delay") or 0)
    if body.get("stream"):

        async def gen():
            yield b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
            if delay:
                await asyncio.sleep(delay)
            payload = '{"choices":[],"usage":' + json.dumps(MOCK_USAGE) + "}"
            yield f"data: {payload}\n\n".encode()
            yield b"data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")
    if delay:
        await asyncio.sleep(delay)
    return {"choices": [{"message": {"role": "assistant", "content": "hi"}}], "usage": MOCK_USAGE}


# Bypass ambient (e.g. macOS system-level) proxies so loopback upstream calls
# from the gateway under test never leave the machine.
class _NoProxyAsyncClient(httpx.AsyncClient):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("trust_env", False)
        super().__init__(*args, **kwargs)


httpx.AsyncClient = _NoProxyAsyncClient

from app.main import app as gateway_app  # noqa: E402


def _serve(app, port: int) -> None:
    asyncio.run(uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")).serve())


def _wait_ready(url: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    with httpx.Client(trust_env=False) as c:
        while time.monotonic() < deadline:
            try:
                if c.get(f"{url}/api/health").status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.1)
    raise RuntimeError(f"gateway at {url} did not become ready")


@pytest.fixture(scope="session", autouse=True)
def servers():
    threading.Thread(target=_serve, args=(mock_upstream, UPSTREAM_PORT), daemon=True).start()
    threading.Thread(target=_serve, args=(gateway_app, GATEWAY_PORT), daemon=True).start()
    _wait_ready(GATEWAY_URL)
    yield


@pytest.fixture(scope="session")
def client(servers):
    with httpx.Client(base_url=GATEWAY_URL, timeout=30, trust_env=False) as c:
        yield c


@pytest.fixture(scope="session")
def admin_headers(client) -> dict:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---- helpers ---------------------------------------------------------------

def create_user(client, admin_headers, quota: int) -> tuple[int, dict]:
    """Create a user, return (user_id, auth headers for that user)."""
    username = f"t_{uuid.uuid4().hex[:10]}"
    password = "pw123456"
    r = client.post(
        "/api/users",
        headers=admin_headers,
        json={"username": username, "password": password, "role": "user", "quota": quota},
    )
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


def create_token(client, user_headers, **payload) -> str:
    """Create an API token, return the plaintext sk- key."""
    r = client.post("/api/tokens", headers=user_headers, json={"name": "t1", **payload})
    assert r.status_code == 200, r.text
    return r.json()["api_key"]


def get_quota(client, user_headers) -> int:
    r = client.get("/api/auth/me", headers=user_headers)
    assert r.status_code == 200, r.text
    return r.json()["quota"]


def chat(client, api_key: str, **body) -> httpx.Response:
    """POST /v1/chat/completions with the gateway key; body fully consumed."""
    payload = {"model": "m", "messages": []}
    payload.update(body)
    return client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
    )
