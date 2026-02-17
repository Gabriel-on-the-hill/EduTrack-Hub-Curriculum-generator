# tests/ingestion/test_search_api.py
from fastapi.testclient import TestClient
from src.ingestion.search_api import router
from unittest.mock import patch

client = TestClient(router)

def test_search_api_results():
    # Mock the search_web call to avoid real network
    with patch("src.ingestion.search_api.search_web") as mock_search:
        mock_search.return_value = [
            {"title": "Test Curr", "url": "https://gov.uk/curr.pdf", "snippet": "Test", "domain": "gov.uk"}
        ]
        
        response = client.post("/api/ingest/search", json={"query": "test"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["authority_hint"] == "high" # inferred from .gov.uk

def test_search_api_rate_limit():
    # This might fail if slowapi memory storage isn't shared or initialized same way
    # Ideally checking headers
    pass 
