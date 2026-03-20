"""Signed-header request authentication for generator APIs."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

_HEADER_SERVICE = "X-Edutrack-Service"
_HEADER_TIMESTAMP = "X-Edutrack-Timestamp"
_HEADER_NONCE = "X-Edutrack-Nonce"
_HEADER_SIGNATURE = "X-Edutrack-Signature"
_NONCE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


class InMemoryNonceStore:
    """Thread-safe TTL nonce store for replay prevention."""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[tuple[str, str], datetime] = {}
        self._lock = threading.Lock()

    def register(self, service: str, nonce: str, now: datetime) -> bool:
        expires_at = now + timedelta(seconds=self.ttl_seconds)
        key = (service, nonce)
        with self._lock:
            self._purge_expired(now)
            if key in self._entries:
                return False
            self._entries[key] = expires_at
            return True

    def _purge_expired(self, now: datetime) -> None:
        expired = [key for key, expires_at in self._entries.items() if expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)


class SignedHeaderAuth:
    """Reusable validator for EduTrack signed service headers."""

    def __init__(
        self,
        *,
        secrets: dict[str, str] | None = None,
        default_secret: str | None = None,
        max_timestamp_skew_seconds: int = 300,
        nonce_store: InMemoryNonceStore | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.secrets = secrets or _load_service_secrets_from_env()
        self.default_secret = default_secret or os.getenv("EDUTRACK_SIGNING_SECRET")
        self.max_timestamp_skew_seconds = max_timestamp_skew_seconds
        self.nonce_store = nonce_store or InMemoryNonceStore(ttl_seconds=max_timestamp_skew_seconds)
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    async def validate_request(
        self,
        request: Request,
        x_edutrack_service: str | None = Header(None, alias=_HEADER_SERVICE),
        x_edutrack_timestamp: str | None = Header(None, alias=_HEADER_TIMESTAMP),
        x_edutrack_nonce: str | None = Header(None, alias=_HEADER_NONCE),
        x_edutrack_signature: str | None = Header(None, alias=_HEADER_SIGNATURE),
    ) -> None:
        await self._validate(
            request=request,
            service=x_edutrack_service or "",
            timestamp=x_edutrack_timestamp or "",
            nonce=x_edutrack_nonce or "",
            signature=x_edutrack_signature or "",
        )

    async def _validate(
        self,
        *,
        request: Request,
        service: str,
        timestamp: str,
        nonce: str,
        signature: str,
    ) -> None:
        normalized_service = service.strip()
        normalized_timestamp = timestamp.strip()
        normalized_nonce = nonce.strip()
        normalized_signature = signature.strip()

        if not normalized_service or not normalized_timestamp or not normalized_nonce or not normalized_signature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signed authentication headers")

        if not _NONCE_PATTERN.fullmatch(normalized_nonce):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid nonce format")

        request_time = _parse_timestamp(normalized_timestamp)
        now = self.now_provider()
        skew = abs((now - request_time).total_seconds())
        if skew > self.max_timestamp_skew_seconds:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Request timestamp outside allowed skew")

        secret = self._resolve_secret(normalized_service)
        if secret is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unknown calling service")

        body = await request.body()
        expected_signature = _build_signature(
            service=normalized_service,
            timestamp=normalized_timestamp,
            nonce=normalized_nonce,
            body=body,
            secret=secret,
        )
        provided_signature = _normalize_signature(normalized_signature)
        if provided_signature is None or not hmac.compare_digest(provided_signature, expected_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid request signature")

        if not self.nonce_store.register(normalized_service, normalized_nonce, now):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Replay detected")

        request.state.edutrack_service = normalized_service
        request.state.edutrack_request_time = request_time
        request.state.edutrack_nonce = normalized_nonce

    def _resolve_secret(self, service: str) -> str | None:
        if service in self.secrets:
            return self.secrets[service]

        env_key = f"EDUTRACK_SIGNING_SECRET_{_normalize_service_name(service)}"
        env_secret = os.getenv(env_key)
        if env_secret:
            return env_secret

        return self.default_secret

    def dependency(self) -> Callable[..., Any]:
        return self.validate_request


class GeneratorAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware wrapper around ``SignedHeaderAuth``."""

    def __init__(self, app: Any, auth: SignedHeaderAuth) -> None:
        super().__init__(app)
        self.auth = auth

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        try:
            await self.auth._validate(
                request=request,
                service=request.headers.get(_HEADER_SERVICE, ""),
                timestamp=request.headers.get(_HEADER_TIMESTAMP, ""),
                nonce=request.headers.get(_HEADER_NONCE, ""),
                signature=request.headers.get(_HEADER_SIGNATURE, ""),
            )
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        return await call_next(request)


def build_generator_auth_dependency(auth: SignedHeaderAuth | None = None) -> Callable[..., Any]:
    """Return a FastAPI dependency enforcing signed EduTrack headers."""

    validator = auth or SignedHeaderAuth()
    return validator.dependency()


def _normalize_service_name(service: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", service.upper()).strip("_")


def _load_service_secrets_from_env() -> dict[str, str]:
    raw = os.getenv("EDUTRACK_SIGNING_SECRETS_JSON", "")
    if not raw:
        return {}

    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError("EDUTRACK_SIGNING_SECRETS_JSON must be a JSON object")

    secrets: dict[str, str] = {}
    for service, secret in loaded.items():
        if isinstance(service, str) and isinstance(secret, str) and service and secret:
            secrets[service] = secret
    return secrets


def _parse_timestamp(raw_value: str) -> datetime:
    try:
        if raw_value.isdigit():
            return datetime.fromtimestamp(int(raw_value), tz=timezone.utc)

        normalized = raw_value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid timestamp format") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _normalize_signature(signature: str) -> str | None:
    candidate = signature.strip()
    if candidate.startswith("sha256="):
        candidate = candidate.split("=", 1)[1]

    if not re.fullmatch(r"[A-Fa-f0-9]{64}", candidate):
        return None

    return candidate.lower()


def _build_signature(*, service: str, timestamp: str, nonce: str, body: bytes, secret: str) -> str:
    canonical = "\n".join([
        service,
        timestamp,
        nonce,
        hashlib.sha256(body).hexdigest(),
    ])
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


__all__ = [
    "GeneratorAuthMiddleware",
    "InMemoryNonceStore",
    "SignedHeaderAuth",
    "build_generator_auth_dependency",
]
