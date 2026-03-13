import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from typing import Mapping

from fastapi import HTTPException, Request

_HEADER_SERVICE = "X-Edutrack-Service"
_HEADER_TIMESTAMP = "X-Edutrack-Timestamp"
_HEADER_NONCE = "X-Edutrack-Nonce"
_HEADER_SIGNATURE = "X-Edutrack-Signature"

_DEFAULT_SKEW_SECONDS = 300
_DEFAULT_NONCE_TTL_SECONDS = 600


class _NonceStore:
    def __init__(self) -> None:
        self._entries: dict[str, float] = {}
        self._lock = threading.Lock()

    def seen(self, service: str, nonce: str, now: float, ttl: int) -> bool:
        key = f"{service}:{nonce}"
        with self._lock:
            expired = [k for k, exp in self._entries.items() if exp <= now]
            for item in expired:
                self._entries.pop(item, None)

            if key in self._entries:
                return True

            self._entries[key] = now + ttl
            return False


_nonce_store = _NonceStore()


def _shared_secret() -> str:
    secret = os.getenv("EDUTRACK_SHARED_SECRET")
    if not secret:
        raise RuntimeError("EDUTRACK_SHARED_SECRET is not configured")
    return secret


def _body_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _signature_payload(timestamp: str, nonce: str, method: str, path: str, body_hash: str) -> str:
    return f"{timestamp}.{nonce}.{method.upper()}.{path}.{body_hash}"


def _sign_payload(secret: str, payload: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_auth_headers(service_name: str, method: str, path: str, body: bytes = b"") -> Mapping[str, str]:
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    body_hash = _body_hash(body)
    payload = _signature_payload(timestamp, nonce, method, path, body_hash)
    signature = _sign_payload(_shared_secret(), payload)

    return {
        _HEADER_SERVICE: service_name,
        _HEADER_TIMESTAMP: timestamp,
        _HEADER_NONCE: nonce,
        _HEADER_SIGNATURE: signature,
    }


async def validate_signed_request(request: Request) -> None:
    if request.url.path.endswith("/health"):
        return

    service = request.headers.get(_HEADER_SERVICE)
    timestamp = request.headers.get(_HEADER_TIMESTAMP)
    nonce = request.headers.get(_HEADER_NONCE)
    signature = request.headers.get(_HEADER_SIGNATURE)

    if not all([service, timestamp, nonce, signature]):
        raise HTTPException(status_code=401, detail="Missing required Edutrack auth headers")

    allowed_services = {
        item.strip()
        for item in os.getenv("EDUTRACK_ALLOWED_SERVICES", "").split(",")
        if item.strip()
    }
    if allowed_services and service not in allowed_services:
        raise HTTPException(status_code=401, detail="Unknown Edutrack service")

    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid timestamp header") from exc

    now = int(time.time())
    skew_seconds = int(os.getenv("EDUTRACK_TIMESTAMP_SKEW_SECONDS", str(_DEFAULT_SKEW_SECONDS)))
    if abs(now - ts) > skew_seconds:
        raise HTTPException(status_code=401, detail="Timestamp outside allowed skew")

    nonce_ttl = int(os.getenv("EDUTRACK_NONCE_TTL_SECONDS", str(_DEFAULT_NONCE_TTL_SECONDS)))
    if _nonce_store.seen(service, nonce, float(now), nonce_ttl):
        raise HTTPException(status_code=403, detail="Nonce replay detected")

    body = await request.body()
    payload = _signature_payload(timestamp, nonce, request.method, request.url.path, _body_hash(body))
    expected_signature = _sign_payload(_shared_secret(), payload)

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=403, detail="Invalid Edutrack signature")
