
import pytest
from src.utils.model_router import ModelRouter, TaskType

@pytest.fixture
def router():
    return ModelRouter()

def test_prioritize_reasoning(router):
    available = [
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-r1:free",
        "mistralai/mistral-7b-instruct:free"
    ]
    # Expect deepseek-r1 first
    prioritized = router.prioritize_models(TaskType.REASONING, available)
    assert prioritized[0] == "deepseek/deepseek-r1:free"
    assert "google/gemini-2.0-flash-exp:free" in prioritized

def test_prioritize_creative(router):
    available = [
        "meta-llama/llama-3-8b-instruct:free",
        "mistralai/mistral-large-2402:free", # huge param
        "google/gemini-2.0-flash-exp:free"
    ]
    # Expect large model or specific creative model
    prioritized = router.prioritize_models(TaskType.CREATIVE, available)
    # mistral-large has "large" -> creative filter?
    # Let's check filter logic. "large" was in creative filter.
    assert "mistralai/mistral-large-2402:free" in prioritized[0] or "70b" in prioritized[0]
    # Actually logic puts high param first.
    
    # Let's test standard fallback
    assert len(prioritized) == 3

def test_prioritize_formatting(router):
    available = [
        "deepseek/deepseek-r1:free",
        "google/gemini-2.0-flash-exp:free", # has "flash"
        "meta-llama/llama-3-8b-instruct:free" # has "8b"
    ]
    prioritized = router.prioritize_models(TaskType.FORMATTING, available)
    # Flash or 8b should be top
    assert "flash" in prioritized[0] or "8b" in prioritized[0]
    
def test_unknown_task_returns_all(router):
    available = ["model-a", "model-b"]
    prioritized = router.prioritize_models(TaskType.STANDARD, available)
    assert prioritized == available
