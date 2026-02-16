
import pytest
from unittest.mock import MagicMock, patch
from src.utils.gemini_client import OpenRouterClient, GeminiModel
from src.utils.model_router import TaskType

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

@pytest.fixture
def client(mock_env):
    return OpenRouterClient()

def test_call_api_success_first_model(client):
    """Verify happy path: first model works."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Success content"}}]
        }
        mock_post.return_value = mock_response
        
        messages = [{"role": "user", "content": "hi"}]
        models = ["model-a", "model-b"]
        
        result = client._call_api(messages, models, 0.7)
        
        assert result == "Success content"
        # Should only have called once with model-a
        assert mock_post.call_count == 1
        assert mock_post.call_args[1]["json"]["model"] == "model-a"

def test_call_api_fallback_on_404(client):
    """Verify fallback: first 404s, second works."""
    with patch("requests.post") as mock_post:
        # sequence of side effects
        resp_fail = MagicMock()
        resp_fail.status_code = 404
        
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {
            "choices": [{"message": {"content": "Fallback content"}}]
        }
        
        mock_post.side_effect = [resp_fail, resp_ok]
        
        messages = [{"role": "user", "content": "hi"}]
        models = ["model-a", "model-b"]
        
        # Should log warning but not crash
        result = client._call_api(messages, models, 0.7)
        
        assert result == "Fallback content"
        assert mock_post.call_count == 2
        # First call model-a
        assert mock_post.call_args_list[0][1]["json"]["model"] == "model-a"
        # Second call model-b
        assert mock_post.call_args_list[1][1]["json"]["model"] == "model-b"

def test_generate_text_integrates_router(client):
    """Verify generate_text calls router and passes list."""
    with patch.object(client, "_call_api", return_value="Routed") as mock_call_api:
        # We don't need to await here because we're mocking the internal sync call?
        # No, generate_text is async and calls asyncio.to_thread(_call_api)
        # So mocking _call_api works on the instance.
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # If we pass GeminiModel.PRO, should use REASONING task
        result = loop.run_until_complete(
            client.generate_text("prompt", model=GeminiModel.PRO)
        )
        
        assert result == "Routed"
        
        # Verify _call_api was called with a list, not string
        args = mock_call_api.call_args
        # args[0] is (messages, models, temperature)
        # We can't easily check exact list contents without hardcoding router logic,
        # but we can check it IS a list
        models_arg = args[0][1]
        assert isinstance(models_arg, list)
        assert len(models_arg) > 0
        loop.close()

def test_generate_structured_uses_formatting(client):
    """Verify generate_structured defaults to formatting."""
    with patch.object(client, "_call_api", return_value='{"foo": "bar"}') as mock_call_api:
        from pydantic import BaseModel
        class TestSchema(BaseModel):
            foo: str
            
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            client.generate_structured("prompt", TestSchema)
        )
        
        assert result.foo == "bar"
        
        # Check models arg was list
        args = mock_call_api.call_args
        models_arg = args[0][1]
        assert isinstance(models_arg, list)
        
        # Should be FORMATTING models by default
        # We can verify by checking if the list matches router.FORMATTING_MODELS
        # or just checking length
        assert len(models_arg) > 1 
        loop.close()
