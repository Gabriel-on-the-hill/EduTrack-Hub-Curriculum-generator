"""Versioned API surface for generation requests."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from src.schemas.generation import GenerationRequest

router = APIRouter(prefix="/v1", tags=["generation"])


@router.post("/generate")
def generate(payload: dict) -> dict:
    """Validate and normalize incoming generation request payload."""
    try:
        request = GenerationRequest.model_validate(payload)
    except ValidationError as exc:
        issues: list[dict[str, object]] = []
        for error in exc.errors():
            loc = [str(part) for part in error.get("loc", [])]
            field = ".".join(loc)
            issue: dict[str, object] = {
                "field": field,
                "code": error.get("type", "validation_error"),
                "message": error.get("msg", "Invalid value"),
            }
            if field == "request_type":
                issue["allowed_values"] = ["lesson_plan", "quiz", "summary"]
            issues.append(issue)

        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "issues": issues},
        ) from exc

    return {
        "ok": True,
        "request": request.model_dump(mode="json"),
    }
