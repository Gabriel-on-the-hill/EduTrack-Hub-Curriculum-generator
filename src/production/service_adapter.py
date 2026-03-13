from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import sessionmaker

from src.api.generation_jobs import get_engine
from src.production.harness import ModelProvenance, ProductionHarness
from src.production.security import ReadOnlySession


@dataclass
class GenerationRuntimeConfig:
    jurisdiction: str
    topic_title: str
    topic_description: str
    content_format: str
    target_level: str
    grade: str


class GenerationServiceAdapter:
    """Adapter for invoking production generation internals and normalizing responses."""

    def _get_readonly_session(self):
        engine = get_engine()
        session_cls = sessionmaker(bind=engine, class_=ReadOnlySession)
        return session_cls()

    def generate(self, *, curriculum_id: str, request_payload: dict[str, Any]) -> dict[str, Any]:
        config = GenerationRuntimeConfig(
            jurisdiction=request_payload.get("jurisdiction", "National"),
            topic_title=request_payload.get("topic_title", "General Topic"),
            topic_description=request_payload.get("topic_description", "Generate curriculum artifact"),
            content_format=request_payload.get("content_format", "lesson_plan"),
            target_level=request_payload.get("target_level", "intermediate"),
            grade=request_payload.get("grade", "General"),
        )

        provenance = request_payload.get("provenance") or {
            "curriculum_id": curriculum_id,
            "source_list": [],
            "retrieval_timestamp": "unknown",
            "extraction_confidence": 1.0,
        }

        session = self._get_readonly_session()
        harness = ProductionHarness(
            db_session=session,
            primary_provenance=ModelProvenance(model_id="gemini-2.0-flash", model_version="2.0"),
            shadow_provenance=ModelProvenance(model_id="gemini-2.0-pro", model_version="2.0"),
            verify_db_level=False,
        )

        try:
            output = asyncio.run(
                harness.generate_artifact(
                    curriculum_id=curriculum_id,
                    config=config,
                    provenance=provenance,
                )
            )
            return {
                "status": "succeeded",
                "result": {
                    "content_markdown": output.content_markdown,
                    "metrics": output.metrics or {},
                    "metadata": output.metadata or {},
                },
            }
        except Exception as exc:  # normalized failure payload
            return {
                "status": "failed",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "retryable": True,
                },
            }
        finally:
            session.close()
