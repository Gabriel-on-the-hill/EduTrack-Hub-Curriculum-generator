"""Mapping layer between Hub UI labels and backend generation enums."""

from __future__ import annotations

from dataclasses import dataclass

from src.schemas.base import GenerationRequestType


UI_TO_BACKEND_REQUEST_TYPE: dict[str, GenerationRequestType] = {
    "Teacher Guide": GenerationRequestType.LESSON_PLAN,
    "Exam Paper": GenerationRequestType.QUIZ,
    "Student Worksheet": GenerationRequestType.SUMMARY,
}


@dataclass
class HubMappingError(ValueError):
    """Raised when Hub sends an unsupported UI label."""

    field: str
    value: object
    allowed_values: list[str]

    def to_422_detail(self) -> dict[str, object]:
        return {
            "error": "validation_error",
            "issues": [
                {
                    "field": self.field,
                    "code": "unsupported_value",
                    "message": (
                        f"Unsupported value '{self.value}' for '{self.field}'."
                    ),
                    "allowed_values": self.allowed_values,
                }
            ],
        }


def map_ui_request_type(label: str) -> GenerationRequestType:
    """Convert a Hub display label to backend enum value."""
    mapped = UI_TO_BACKEND_REQUEST_TYPE.get(label)
    if mapped is None:
        raise HubMappingError(
            field="request_type",
            value=label,
            allowed_values=sorted(UI_TO_BACKEND_REQUEST_TYPE.keys()),
        )
    return mapped
