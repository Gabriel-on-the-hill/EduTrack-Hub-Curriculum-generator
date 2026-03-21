"""
Admin API header authentication helpers.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from threading import Lock

from fastapi import HTTPException, Request


_replay_cache: dict[str, int] = {}
_replay_lock = Lock()


def _get_secret() -> str:
    secret = os.getenv("ADMIN_AUTH_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Admin auth secret is not configured")
    return secret


def _max_skew_seconds() -> int:
    return int(os.getenv("ADMIN_AUTH_MAX_SKEW_SECONDS", "300"))


def _body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def build_signature(secret: str, timestamp: str, nonce: str, method: str, path: str, body: bytes) -> str:
    payload = "\n".join(
        [
            timestamp,
            nonce,
            method.upper(),
            path,
            _body_digest(body),
        ]
    ).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def reset_replay_cache() -> None:
    with _replay_lock:
        _replay_cache.clear()


def _check_timestamp(timestamp_header: str, now: int) -> int:
    try:
        timestamp = int(timestamp_header)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid admin auth timestamp") from exc

    if abs(now - timestamp) > _max_skew_seconds():
        raise HTTPException(status_code=401, detail="Stale admin auth timestamp")
    return timestamp


def _check_replay(nonce: str, timestamp: int, now: int) -> None:
    with _replay_lock:
        expired_before = now - _max_skew_seconds()
        stale_nonces = [key for key, seen_at in _replay_cache.items() if seen_at < expired_before]
        for key in stale_nonces:
            del _replay_cache[key]

        if nonce in _replay_cache:
            raise HTTPException(status_code=401, detail="Replay detected for admin auth nonce")

        _replay_cache[nonce] = timestamp


async def verify_admin_headers(request: Request) -> None:
    secret = _get_secret()
    timestamp_header = request.headers.get("X-Admin-Timestamp")
    nonce = request.headers.get("X-Admin-Nonce")
    signature = request.headers.get("X-Admin-Signature")

    if not timestamp_header or not nonce or not signature:
        raise HTTPException(status_code=401, detail="Missing admin auth headers")

    now = int(time.time())
    timestamp = _check_timestamp(timestamp_header, now)
    body = await request.body()
    expected_signature = build_signature(
        secret=secret,
        timestamp=timestamp_header,
        nonce=nonce,
        method=request.method,
        path=request.url.path,
        body=body,
    )
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid admin auth signature")

    _check_replay(nonce, timestamp, now)
