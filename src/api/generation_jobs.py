from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///demo.db")


def get_engine():
    return create_engine(_database_url())


def init_generation_job_store() -> None:
    """Create durable generation_jobs table if it does not exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS generation_jobs (
        job_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        request_payload TEXT,
        result_payload TEXT,
        error_payload TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """
    with get_engine().begin() as conn:
        conn.execute(text(ddl))


@contextmanager
def _tx():
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def _utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def create_job(job_id: str, payload: dict[str, Any]) -> None:
    now = _utc_iso()
    with _tx() as conn:
        conn.execute(
            text(
                """
                INSERT INTO generation_jobs (
                    job_id, status, request_payload, created_at, updated_at
                ) VALUES (
                    :job_id, :status, :request_payload, :created_at, :updated_at
                )
                """
            ),
            {
                "job_id": job_id,
                "status": "queued",
                "request_payload": json.dumps(payload),
                "created_at": now,
                "updated_at": now,
            },
        )


def update_status(job_id: str, status: str, *, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> None:
    now = _utc_iso()
    with _tx() as conn:
        conn.execute(
            text(
                """
                UPDATE generation_jobs
                SET status = :status,
                    result_payload = COALESCE(:result_payload, result_payload),
                    error_payload = COALESCE(:error_payload, error_payload),
                    updated_at = :updated_at
                WHERE job_id = :job_id
                """
            ),
            {
                "job_id": job_id,
                "status": status,
                "result_payload": json.dumps(result) if result is not None else None,
                "error_payload": json.dumps(error) if error is not None else None,
                "updated_at": now,
            },
        )


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT job_id, status, request_payload, result_payload, error_payload, created_at, updated_at
                FROM generation_jobs
                WHERE job_id = :job_id
                """
            ),
            {"job_id": job_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "request_payload": json.loads(row["request_payload"]) if row["request_payload"] else None,
        "result_payload": json.loads(row["result_payload"]) if row["result_payload"] else None,
        "error_payload": json.loads(row["error_payload"]) if row["error_payload"] else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
