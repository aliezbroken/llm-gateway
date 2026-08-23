"""Gateway proxy orchestration: auth -> limits -> forward -> usage -> billing -> logs.

Runs inside a single request lifecycle; uses the non-blocking httpx AsyncClient
to stream byte-for-byte to/from the upstream while tracking SSE `usage`.
"""

import json
import time

import httpx
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...config import settings
from ...errors import ErrorCode, raise_http
from ...models import UsageLog, User
from ...modules.system import service as system_service
from ...modules.tokens import service as token_service
from .limiter import limiter as concurrency_limiter
from .usage import SSEUsageTracker, parse_usage_from_json, pick

HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
              "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length"}


def preflight() -> Response:
    import fastapi.responses as fr
    return fr.Response(status_code=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Real-IP, X-Forwarded-For",
    })


def _extract_bearer(auth_header: str) -> str:
    if not auth_header.lower().startswith("bearer "):
        raise raise_http(401, ErrorCode.INVALID_API_KEY, "Missing bearer token", "invalid_request_error")
    return auth_header.split(" ", 1)[1].strip()


def _client_ip(request: Request) -> str:
    """Return real client IP. Trust X-* headers only when direct peer is a trusted loopback proxy."""
    peer = request.client.host if request.client else ""
    if peer in ("127.0.0.1", "::1", "localhost"):
        x_real = request.headers.get("x-real-ip")
        if x_real:
            return x_real.strip()
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return peer


def _upstream_headers(request: Request) -> dict:
    headers = {}
    for k, v in request.headers.items():
        if k.lower() not in HOP_BY_HOP and not k.lower().startswith("x-"):
            headers[k] = v
    if "accept-encoding" not in headers:
        pass  # let httpx handle
    return headers


def _prepare_body(body: bytes) -> tuple[bool, bytes, dict]:
    """Ensure stream_options.include_usage is set so we always receive token usage."""
    raw = {}
    try:
        raw = json.loads(body)
    except json.JSONDecodeError:
        return False, body, {}
    is_stream = bool(raw.get("stream"))
    if is_stream:
        raw.setdefault("stream_options", {})["include_usage"] = True
        return True, json.dumps(raw).encode(), raw
    return False, body, raw


def _compute_cost(db: Session, model: str, prompt: int, completion: int) -> int:
    ratios = system_service.get_model_ratios(db)
    r = ratios.get(model, {})
    p_ratio = r.get("prompt", 1.0)
    c_ratio = r.get("completion", 1.0)
    return int(round(prompt * p_ratio + completion * c_ratio))


def _finalize(db: Session, user: User, token, ctx: dict, usage_dict: dict | None,
              latency_ms: float, status: str = "ok", error_code: str = "") -> dict:
    """Charge quota and persist a usage log entry. Returns result dict (used by tests too)."""
    model = ctx.get("model", "")
    prompt = pick(usage_dict, "prompt_tokens")
    completion = pick(usage_dict, "completion_tokens")
    total = prompt + completion
    cost = _compute_cost(db, model, prompt, completion) if usage_dict else 0
    try:
        # `user` was loaded at request start; a long stream may outlive concurrent
        # charges and admin grants. Re-read the balance or the stale snapshot would
        # overwrite them (wiping a fresh grant -> premature 402 out of credits).
        db.refresh(user)
        if cost > user.quota:
            cost = user.quota
        user.quota -= cost
    except Exception:  # noqa: BLE001 - billing must never crash a served response
        db.rollback()
        cost = 0
    log = UsageLog(
        user_id=user.id,
        token_id=token.id,
        token_name=token.name,
        client_ip=ctx.get("client_ip", ""),
        model=model,
        endpoint=ctx.get("path", ""),
        request_id=ctx.get("request_id", ""),
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        quota_cost=cost,
        latency_ms=round(latency_ms, 2),
        status=status,
        error_code=error_code,
    )
    db.add(log)
    try:
        db.commit()
    except Exception:  # noqa: BLE001 - billing must never crash a served response
        db.rollback()
    return {"prompt": prompt, "completion": completion, "total": total, "cost": cost}


async def stream_generator(upstream, client, ctx, token, db: Session):
    """Yield upstream body to client; on completion charge quota + write log.

    `upstream` context is already entered by _peek_stream_headers; we read bytes,
    track SSE usage incrementally, and finalize billing exactly once.
    """
    tracker = SSEUsageTracker()
    finalized = False

    def finish():
        nonlocal finalized
        if finalized:
            return
        finalized = True
        latency = (time.perf_counter() - ctx["start"]) * 1000
        code = getattr(upstream, "status_code", 500)
        usage_dict = tracker.usage() if code < 400 else None
        if code < 400 and usage_dict is not None:
            _finalize(db, ctx["user"], token, ctx, usage_dict, latency, status="ok")
        else:
            _finalize(db, ctx["user"], token, ctx, None, latency,
                      status="ok" if code < 400 else "upstream_error",
                      error_code="" if code < 400 else f"HTTP {code}")

    try:
        async for chunk in upstream.aiter_bytes():
            tracker.feed(chunk)
            yield chunk
    except Exception as exc:  # noqa: BLE001 - client disconnect / upstream error
        ctx["upstream_error"] = str(exc)[:60]
    finally:
        finish()
        await concurrency_limiter.release(("token", ctx["token_id"]), ctx["token_limit"])
        await concurrency_limiter.release(("user", ctx["user_id"]), ctx["user_limit"])
        await client.aclose()


async def proxy(request: Request, db: Session):
    api_key = _extract_bearer(request.headers.get("authorization", ""))
    client_ip = _client_ip(request)
    token = token_service.validate_token(db, api_key, client_ip)
    user = db.get(User, token.user_id)
    if user is None or user.status != "active":
        raise raise_http(401, ErrorCode.INVALID_API_KEY, "User disabled or not found", "invalid_request_error")
    if user.quota <= 0:
        raise raise_http(402, ErrorCode.INSUFFICIENT_QUOTA, "Insufficient quota", "invalid_request_error")

    acquired = await _acquire_limits(token.id, token.max_concurrency, user.id, user.max_concurrency)
    if not acquired:
        raise raise_http(429, ErrorCode.CONCURRENCY_LIMIT, "Concurrency limit reached", "invalid_request_error")

    try:
        return await _route(request, db, token, user, client_ip)
    except Exception:
        await _release_limits(token.id, token.max_concurrency, user.id, user.max_concurrency)
        raise


async def _acquire_limits(token_id: int, token_limit: int, user_id: int, user_limit: int) -> bool:
    ok = await concurrency_limiter.acquire(("token", token_id), token_limit)
    if not ok:
        return False
    ok = await concurrency_limiter.acquire(("user", user_id), user_limit)
    if not ok:
        await concurrency_limiter.release_key(("token", token_id))
        return False
    return True


async def _release_limits(token_id: int, token_limit: int, user_id: int, user_limit: int) -> None:
    await concurrency_limiter.release(("token", token_id), token_limit)
    await concurrency_limiter.release(("user", user_id), user_limit)


async def _route(request: Request, db: Session, token, user, client_ip: str):
    body = await request.body()
    is_stream, out_body, raw = _prepare_body(body)
    upstream_url = system_service.get_upstream_url(db, settings.upstream_url).rstrip("/")
    full_path = request.url.path
    url = f"{upstream_url}{full_path}"
    ctx = {
        "user": user, "user_id": user.id, "client_ip": client_ip, "path": full_path,
        "model": raw.get("model", ""), "request_id": "",
        "start": time.perf_counter(),
        "token_id": token.id,
        "token_limit": token.max_concurrency,
        "user_limit": user.max_concurrency,
    }
    headers = _upstream_headers(request)

    if is_stream:
        client = httpx.AsyncClient(timeout=None)
        req = client.build_request(request.method, url, headers=headers, content=out_body)
        upstream = await client.send(req, stream=True)
        resp_headers = _build_stream_headers(upstream)
        return StreamingResponse(
            stream_generator(upstream, client, ctx, token, db),
            status_code=resp_headers[0],
            headers=resp_headers[1],
            media_type=resp_headers[2],
        )
    return await _plain(request.method, url, headers, out_body, ctx, token, db)


def _build_stream_headers(response):
    headers = {k: v for k, v in response.headers.items()
               if k.lower() not in HOP_BY_HOP | {"content-encoding", "content-length", "content-type"}}
    media = response.headers.get("content-type", "text/event-stream")
    return response.status_code, headers, media


async def _plain(method: str, url: str, headers: dict, body: bytes, ctx, token, db: Session) -> Response:
    start = ctx["start"]
    client = httpx.AsyncClient(timeout=httpx.Timeout(600.0))
    try:
        upstream = await client.request(method, url, headers=headers, content=body)
        latency_ms = (time.perf_counter() - start) * 1000
        usage_dict = parse_usage_from_json(upstream.content) if upstream.status_code < 400 else None
        _finalize(db, ctx["user"], token, ctx, usage_dict, latency_ms,
                  status="ok" if upstream.status_code < 400 else "upstream_error",
                  error_code="" if upstream.status_code < 400 else f"HTTP {upstream.status_code}")
        headers_out = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP}
        return Response(content=upstream.content, status_code=upstream.status_code, headers=headers_out)
    finally:
        await concurrency_limiter.release(("token", ctx["token_id"]), ctx["token_limit"])
        await concurrency_limiter.release(("user", ctx["user_id"]), ctx["user_limit"])
        await client.aclose()

