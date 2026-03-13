import os
from sqlalchemy import text

from src.ingestion.services import save_resource, get_engine


def test_save_resource_persists_with_provenance(tmp_path):
    db_path = tmp_path / "resource_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    resource_id = save_resource(
        curriculum_id="ng-bio-ss1",
        title="Cell Division",
        content_markdown="# lesson",
        provenance_metadata={"generator_job_id": "job-1", "status": "succeeded"},
    )

    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, curriculum_id, title FROM resources WHERE id = :id"),
            {"id": resource_id},
        ).fetchone()

    assert row is not None
    assert row[1] == "ng-bio-ss1"
