import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import urljoin

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/generator", tags=["generator"])

REQUEST_TIMEOUT_SECONDS = 30
SIGNATURE_HEADER = "X-Edutrack-Signature"
TIMESTAMP_HEADER = "X-Edutrack-Timestamp"


class GeneratorJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: str | None = None
    curriculum_id: str | None = None
    options: dict[str, Any] | None = None


def _get_generator_config() -> tuple[str, str]:
    base_url = os.getenv("GENERATOR_BASE_URL", "").strip()
    shared_secret = os.getenv("GENERATOR_SHARED_SECRET", "").strip()

    if not base_url or not shared_secret:
        raise HTTPException(
            status_code=500,
            detail="Generator service is not configured.",
        )

    normalized_base_url = base_url.rstrip("/") + "/"
    return normalized_base_url, shared_secret


def _canonical_body(payload: Any) -> str:
    if payload is None:
        return ""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _build_signature(
    secret: str,
    method: str,
    path: str,
    timestamp: str,
    body: str,
) -> str:
    signing_payload = "\n".join([method.upper(), path, timestamp, body])
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_payload.encode("utf-8"),
        hashlib.sha256,
    )
    return digest.hexdigest()


def _proxy_generator_request(method: str, path: str, payload: Any | None = None) -> Any:
    base_url, shared_secret = _get_generator_config()
    url = urljoin(base_url, path.lstrip("/"))
    timestamp = str(int(time.time()))
    body = _canonical_body(payload)
    signature = _build_signature(shared_secret, method, path, timestamp, body)
    headers = {
        TIMESTAMP_HEADER: timestamp,
        SIGNATURE_HEADER: signature,
    }

    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to contact generator service.",
        ) from exc

    if response.status_code >= 500:
        raise HTTPException(status_code=502, detail="Generator service error.")

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Generator service returned invalid JSON.",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response_payload)

    return response_payload


@router.post("/jobs")
def create_generator_job(job: GeneratorJobCreateRequest) -> Any:
    payload = job.model_dump(exclude_none=True)
    return _proxy_generator_request("POST", "/v1/generate", payload)


@router.get("/jobs/{job_id}")
def get_generator_job(job_id: str) -> Any:
    safe_job_id = job_id.strip()
    if not safe_job_id:
        raise HTTPException(status_code=400, detail="job_id is required.")
    return _proxy_generator_request("GET", f"/v1/jobs/{safe_job_id}")
