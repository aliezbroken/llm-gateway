"""Quota/billing regression tests.

Every mock-upstream request costs REQUEST_COST (=20) quota units.
"""

import threading
import time

import httpx

from .conftest import GATEWAY_URL, REQUEST_COST, chat, create_token, create_user, get_quota


def test_user_quota_blocks_only_when_exhausted(client, admin_headers):
    """402 must fire only when the balance is actually used up, not earlier."""
    _, headers = create_user(client, admin_headers, quota=REQUEST_COST)
    api_key = create_token(client, headers)

    r = chat(client, api_key)
    assert r.status_code == 200, r.text
    assert get_quota(client, headers) == 0

    r = chat(client, api_key)
    assert r.status_code == 402, r.text


def test_token_quota_limit_blocks_only_when_reached(client, admin_headers):
    """Token quota_limit is a hard cap on accumulated usage; 402 only at the cap."""
    _, headers = create_user(client, admin_headers, quota=100_000)
    api_key = create_token(client, headers, quota_limit=2 * REQUEST_COST)

    assert chat(client, api_key).status_code == 200  # used 20
    assert chat(client, api_key).status_code == 200  # used 40 == limit

    r = chat(client, api_key)
    assert r.status_code == 402, r.text


def test_token_quota_limit_zero_means_unlimited(client, admin_headers):
    """Regression: quota_limit=0 must mean "no cap" (UI copy says 留空或 0 表示不限制).

    Before the fix, validate_token checked `quota_limit is not None`, so 0 made
    `used >= 0` always true -> every request was rejected with 402 up front.
    """
    _, headers = create_user(client, admin_headers, quota=100_000)
    api_key = create_token(client, headers, quota_limit=0)

    r = chat(client, api_key)
    assert r.status_code == 200, r.text
    assert chat(client, api_key).status_code == 200


def test_stream_finalize_does_not_overwrite_concurrent_grant(client, admin_headers):
    """Regression: a long streaming request must not wipe a concurrent balance change.

    The gateway loads the User row at request start. Before the fix, billing at
    stream end wrote back that stale snapshot (quota - cost), discarding any
    grant made while the stream was in flight -- the next request then failed
    with 402 "Insufficient quota" despite the fresh grant.
    """
    uid, headers = create_user(client, admin_headers, quota=2 * REQUEST_COST)
    api_key = create_token(client, headers)  # unlimited token

    # Warm request: 40 - 20 = 20.
    assert chat(client, api_key).status_code == 200
    assert get_quota(client, headers) == REQUEST_COST

    # Slow streaming request starts now; its session snapshots quota=20.
    result = {}

    def background_request():
        # own client: this runs on its own thread
        with httpx.Client(base_url=GATEWAY_URL, timeout=30, trust_env=False) as c:
            result["resp"] = chat(c, api_key, stream=True, mock_delay=2)

    t = threading.Thread(target=background_request)
    t.start()
    time.sleep(0.5)  # let the gateway pass its pre-checks and start streaming

    # Admin grants quota while the stream is in flight.
    r = client.post(f"/api/users/{uid}/quota", headers=admin_headers,
                    json={"delta": 10_000, "reason": "grant"})
    assert r.status_code == 200, r.text

    t.join(timeout=30)
    assert not t.is_alive()
    assert result["resp"].status_code == 200, result["resp"].text

    # 40 - 20 (warm) - 20 (slow stream) + 10000 (grant) = 10000.
    assert get_quota(client, headers) == 10_000

    # The next request must NOT be rejected as out-of-credits.
    r = chat(client, api_key)
    assert r.status_code == 200, r.text
