import json

from src.production.resource_storage import (
    build_hub_resource_citations,
    build_hub_source_attribution,
    persist_hub_resource_output,
)


def test_persist_hub_resource_output_is_idempotent(tmp_path):
    citations = [
        {
            "competency_id": "comp-1",
            "sources": [
                {
                    "url": "https://example.edu/curriculum.pdf",
                    "authority": "Example Ministry",
                    "fetch_date": "2026-03-20",
                }
            ],
        }
    ]
    source_attribution = build_hub_source_attribution(
        [{"url": "https://example.edu/curriculum.pdf", "authority": "Example Ministry", "fetch_date": "2026-03-20"}]
    )

    first = persist_hub_resource_output(
        content="# Generated lesson",
        curriculum_id="curr-123",
        competency_ids=["comp-1"],
        citations=citations,
        source_attribution=source_attribution,
        generation_timestamp="2026-03-20T10:00:00+00:00",
        job_id="job-1",
        storage_root=tmp_path,
    )
    second = persist_hub_resource_output(
        content="# Generated lesson",
        curriculum_id="curr-123",
        competency_ids=["comp-1"],
        citations=citations,
        source_attribution=source_attribution,
        generation_timestamp="2026-03-20T11:00:00+00:00",
        job_id="job-2",
        storage_root=tmp_path,
    )

    assert first["created"] is True
    assert second["created"] is False
    assert first["output_id"] == second["output_id"]
    assert first["storage_path"] == second["storage_path"]

    with open(first["storage_path"], "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["output_id"] == first["output_id"]
    assert payload["metadata"]["job_id"] == "job-1"
    assert payload["metadata"]["generation_timestamp"] == "2026-03-20T10:00:00+00:00"


def test_build_hub_resource_citations_tracks_each_competency():
    citations = build_hub_resource_citations(
        competency_ids=["comp-1", "comp-2"],
        source_list=[
            {
                "url": "https://example.edu/curriculum.pdf",
                "authority": "Example Ministry",
                "fetch_date": "2026-03-20",
            }
        ],
    )

    assert [citation["competency_id"] for citation in citations] == ["comp-1", "comp-2"]
    assert citations[0]["sources"][0]["authority"] == "Example Ministry"
