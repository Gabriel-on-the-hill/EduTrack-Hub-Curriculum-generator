# Phase 2 - Curriculum Hunter

## Run API
uvicorn src.api.main:app --reload

## Run Tests
pytest tests/ingestion

## Health Check
GET /v1/health

## Sync Test
POST /v1/ingest
{
  "url": "https://example.gov/sample.pdf"
}

## Search Test
POST /v1/ingest/search
{
  "query": "math curriculum"
}
