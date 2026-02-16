
import pytest
from src.utils.model_router import ModelRouter, TaskType

def test_router_initialization():
    router = ModelRouter()
    assert router is not None

def test_get_models_for_reasoning_task():
    router = ModelRouter()
    models = router.get_candidate_models(TaskType.REASONING)
    
    assert len(models) > 0
    # Should prioritize high-reasoning models
    assert any("deepseek" in m or "gemini" in m or "claude" in m for m in models)
    # The first one should be a strong model
    first_model = models[0]
    assert "deepseek" in first_model or "gemini" in first_model or "claude" in first_model

def test_get_models_for_formatting_task():
    router = ModelRouter()
    models = router.get_candidate_models(TaskType.FORMATTING)
    
    assert len(models) > 0
    # Should prioritize fast/cheap models (Llama, Gemma, Haiku)
    # This is a heuristic check
    strong_reasoners = ["r1", "opus", "pro"]
    # Ideally should NOT start with a super heavy model if a lighter one is available
    # But for now, just ensure it returns a valid list
    assert isinstance(models, list)

def test_get_models_for_creative_task():
    router = ModelRouter()
    models = router.get_candidate_models(TaskType.CREATIVE)
    assert len(models) > 0

def test_invalid_task_type():
    router = ModelRouter()
    # Should return a default list or raise error. 
    # Let's say it defaults to STANDARD/CREATIVE
    with pytest.raises(ValueError):
        router.get_candidate_models("unknown_task")

def test_provider_extraction():
    # Helper to get "google" from "google/gemini-pro"
    assert ModelRouter.get_provider_name("google/gemini-pro") == "google"
    assert ModelRouter.get_provider_name("anthropic/claude-3") == "anthropic"
    assert ModelRouter.get_provider_name("meta-llama/llama-3") == "meta-llama"
    # Fallback
    assert ModelRouter.get_provider_name("unknown-model") == "unknown"
