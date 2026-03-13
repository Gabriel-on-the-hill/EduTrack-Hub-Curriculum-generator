# Phase 2 - Curriculum Hunter

## Run API
uvicorn src.api.main:app --reload

## Run Tests
pytest tests/ingestion

## Sync Test
POST /ingest
{
  "url": "https://example.gov/sample.pdf"
}
