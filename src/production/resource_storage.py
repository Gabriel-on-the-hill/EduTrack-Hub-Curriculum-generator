"""
Hub Resource Storage helpers.

Persists generated Hub resources to local object-style storage using a
deterministic output identifier so repeated save attempts remain idempotent.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5


def _default_storage_root() -> Path:
    """Resolve the Hub resource storage root."""
    return Path(os.getenv("HUB_RESOURCE_STORAGE_PATH", "hub_resource_storage"))


def _normalize_json(value: Any) -> str:
    """Serialize nested values deterministically for hashing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def build_hub_resource_citations(
    competency_ids: list[str],
    source_list: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Build minimal citation metadata for persisted Hub resources.

    Each selected competency is linked to the known source list so the saved
    resource keeps explicit grounding metadata.
    """
    sources = source_list or []
    return [
        {
            "competency_id": competency_id,
            "sources": [
                {
                    "url": source.get("url"),
                    "authority": source.get("authority"),
                    "fetch_date": source.get("fetch_date"),
                }
                for source in sources
            ],
        }
        for competency_id in competency_ids
    ]


def build_hub_source_attribution(
    source_list: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the persisted source attribution block."""
    sources = source_list or []
    primary_source = sources[0] if sources else {}
    authority = primary_source.get("authority")
    source_url = primary_source.get("url")

    if authority and source_url:
        attribution_text = f"Based on official curriculum from: {authority} · {source_url}"
    elif source_url:
        attribution_text = f"Based on official curriculum from: {source_url}"
    else:
        attribution_text = "Based on official curriculum sources captured at generation time."

    return {
        "attribution_text": attribution_text,
        "primary_source": {
            "authority": authority,
            "url": source_url,
            "fetch_date": primary_source.get("fetch_date"),
        },
        "sources": sources,
    }


def persist_hub_resource_output(
    *,
    content: str,
    curriculum_id: str,
    competency_ids: list[str],
    citations: list[dict[str, Any]],
    source_attribution: dict[str, Any],
    generation_timestamp: str,
    job_id: str,
    storage_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Persist a generated Hub resource using deterministic idempotency.

    Repeated calls with the same curriculum/competency/content/citation payload
    return the existing stored record instead of creating duplicates.
    """
    root = Path(storage_root) if storage_root else _default_storage_root()
    root.mkdir(parents=True, exist_ok=True)

    normalized_competency_ids = sorted(competency_ids)
    idempotency_payload = {
        "curriculum_id": curriculum_id,
        "competency_ids": normalized_competency_ids,
        "content": content,
        "citations": citations,
        "source_attribution": source_attribution,
    }
    idempotency_key = hashlib.sha256(_normalize_json(idempotency_payload).encode("utf-8")).hexdigest()
    output_id = str(uuid5(NAMESPACE_URL, idempotency_key))

    resource_dir = root / "resources"
    resource_dir.mkdir(parents=True, exist_ok=True)
    resource_path = resource_dir / f"{output_id}.json"

    if resource_path.exists():
        with resource_path.open("r", encoding="utf-8") as handle:
            existing = json.load(handle)
        return {
            "created": False,
            "output_id": output_id,
            "storage_path": str(resource_path),
            "record": existing,
        }

    persisted_at = datetime.now(tz=timezone.utc).isoformat()
    record = {
        "output_id": output_id,
        "content": content,
        "metadata": {
            "curriculum_id": curriculum_id,
            "competency_ids": normalized_competency_ids,
            "citations": citations,
            "source_attribution": source_attribution,
            "generation_timestamp": generation_timestamp,
            "job_id": job_id,
            "persisted_at": persisted_at,
            "idempotency_key": idempotency_key,
        },
    }

    with resource_path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)

    return {
        "created": True,
        "output_id": output_id,
        "storage_path": str(resource_path),
        "record": record,
    }
