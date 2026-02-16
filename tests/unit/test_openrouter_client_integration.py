
import pytest
from unittest.mock import MagicMock, patch
from src.utils.gemini_client import OpenRouterClient, GeminiModel
from src.utils.model_router import TaskType

@pytest.fixture
def mock_requests():
    # Patch at module level where it is used or imported
    # gemini_client imports requests at top level
    with patch("src.utils.gemini_client.requests") as mock_req:
        # Mock GET /models response
        mock_models_resp = MagicMock()
        mock_models_resp.status_code = 200
        mock_models_resp.json.return_value = {
            "data": [
                {"id": "deepseek/deepseek-r1:free"},
                {"id": "google/gemini-2.0-flash-exp:free"},
                {"id": "meta-llama/llama-3-8b-instruct:free"}
            ]
        }
        mock_req.get.return_value = mock_models_resp
        
        # Mock POST defaults (can be overridden in tests)
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "choices": [{"message": {"content": "Success content"}}]
        }
        mock_req.post.return_value = mock_post_resp
        
        yield mock_req

@pytest.fixture
def client(mock_requests):
    return OpenRouterClient(api_key="fake-key")

def test_init_fetches_models(client, mock_requests):
    """Verify init calls API and filters models."""
    mock_requests.get.assert_called_once()
    assert len(client._free_models) == 3
    assert "deepseek/deepseek-r1:free" in client._free_models

def test_call_api_blacklist_logic(client, mock_requests):
    """Verify 404 adds to blacklist and tries next."""
    # Setup post side effects
    # 1. 404 (model-a)
    resp_404 = MagicMock()
    resp_404.status_code = 404
    
    # 2. 200 (model-b)
    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": "Fallback worked"}}]
    }
    
    mock_requests.post.side_effect = [resp_404, resp_200]
    
    models = ["model-a", "model-b"]
    # Pre-populate free models just in case
    client._free_models = models
    
    result = client._call_api([], models, 0.7)
    
    assert result == "Fallback worked"
    assert "model-a" in client._bad_models
    assert "model-b" not in client._bad_models

def test_generate_text_uses_router_dynamic(client, mock_requests):
    """Verify generate_text calls router with dynamic list."""
    # We patch the router on the client instance
    with patch.object(client._router, "prioritize_models") as mock_prioritize:
        mock_prioritize.return_value = ["mock-selected-model"]
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            client.generate_text("prompt", model=GeminiModel.PRO)
        )
        
        # Should have called prioritize with REASONING and _free_models
        mock_prioritize.assert_called_once_with(TaskType.REASONING, client._free_models)
        
        # Should have called API with selected model
        call_args = mock_requests.post.call_args
        assert call_args[1]["json"]["model"] == "mock-selected-model"
        loop.close()
