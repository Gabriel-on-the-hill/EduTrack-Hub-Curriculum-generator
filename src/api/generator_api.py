from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/generator", tags=["generator"])


class GeneratorJobCreateRequest(BaseModel):
    curriculum_id: str
    topic_title: str
    topic_description: str = ""
    content_format: str
    target_level: str
    requested_by: str = Field(default="hub-admin")


class GeneratorJobCreateResponse(BaseModel):
    job_id: str
    status: str


def _generator_base_url() -> str:
    return os.getenv("GENERATOR_BASE_URL", "http://localhost:8100").rstrip("/")


def _signature_headers(method: str, path: str, body: Dict[str, Any] | None) -> Dict[str, str]:
    secret = os.getenv("GENERATOR_SIGNING_SECRET", "dev-secret")
    ts = str(int(time.time()))
    payload = json.dumps(body or {}, separators=(",", ":"), sort_keys=True)
    canonical = f"{method.upper()}\n{path}\n{ts}\n{payload}"
    signature = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "X-Hub-Timestamp": ts,
        "X-Hub-Signature": signature,
        "X-Hub-Signature-Alg": "hmac-sha256",
        "Content-Type": "application/json",
    }


@router.post("/jobs", response_model=GeneratorJobCreateResponse)
def create_generator_job(req: GeneratorJobCreateRequest):
    path = "/v1/generate"
    payload = req.model_dump()
    try:
        upstream = requests.post(
            f"{_generator_base_url()}{path}",
            json=payload,
            headers=_signature_headers("POST", path, payload),
            timeout=20,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Generator service unavailable: {exc}")

    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.text)

    data = upstream.json()
    return GeneratorJobCreateResponse(job_id=str(data.get("job_id")), status=data.get("status", "queued"))


@router.get("/jobs/{job_id}")
def get_generator_job(job_id: str):
    path = f"/v1/jobs/{job_id}"
    try:
        upstream = requests.get(
            f"{_generator_base_url()}{path}",
            headers=_signature_headers("GET", path, None),
            timeout=20,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Generator service unavailable: {exc}")

    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=upstream.text)

    return upstream.json()
