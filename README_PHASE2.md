# Phase 2 - Curriculum Hunter

## Run API
uvicorn src.ingestion.api:router --reload

## Run Tests
pytest tests/ingestion

## Sync Test
POST /ingest
{
  "url": "https://example.gov/sample.pdf"
}
