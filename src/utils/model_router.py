
from enum import Enum
import random

class TaskType(str, Enum):
    """Types of tasks requiring different model capabilities."""
    REASONING = "reasoning"     # Complex logic, planning, evaluation (high IQ)
    CREATIVE = "creative"       # Content generation, prose, storytelling (high EQ)
    FORMATTING = "formatting"   # Structure, JSON/XML output, simple transforms (fast/cheap)
    STANDARD = "standard"       # General purpose default

class ModelRouter:
    """
    Intelligent router for selecting the best model based on task requirements.
    Optimizes for free-tier availability and performance.
    
    Revised List: Removed unstable/experimental models that caused 404/429 errors.
    """
    
    # Priority lists for different task types (best to worst)
    # Using OpenRouter model IDs
    
    REASONING_MODELS = [
        "deepseek/deepseek-r1:free",             # State-of-the-art reasoning (busy but best)
        "google/gemini-2.0-flash-thinking-exp:free", # Fast reasoning
        "google/gemini-2.0-flash-exp:free",      # Strong generalist fallback (Very Reliable)
        "deepseek/deepseek-chat:free",           # V3 fallback
    ]
    
    CREATIVE_MODELS = [
        "google/gemini-2.0-flash-exp:free",      # Reliable high-context workhorse
        "meta-llama/llama-3-8b-instruct:free",   # Fast, reliable prose
        "mistralai/mistral-7b-instruct:free",    # Classic reliable fallback
        "qwen/qwen-2-7b-instruct:free",          # Good alternative
    ]
    
    FORMATTING_MODELS = [
        "google/gemini-2.0-flash-exp:free",      # Best current free model for JSON structure
        "meta-llama/llama-3-8b-instruct:free",   # Fast & strict
        "google/gemma-2-9b-it:free",             # Reliable
        "openrouter/auto",                       # Fallback to auto-router
    ]
    
    DEFAULT_MODELS = CREATIVE_MODELS

    def get_candidate_models(self, task: TaskType | str) -> list[str]:
        """
        Get a list of candidate models for a specific task, ordered by preference.
        """
        if isinstance(task, str):
            try:
                task = TaskType(task.lower())
            except ValueError:
                raise ValueError(f"Unknown task type: {task}")
        
        if task == TaskType.REASONING:
            return self.REASONING_MODELS
        elif task == TaskType.CREATIVE:
            return self.CREATIVE_MODELS
        elif task == TaskType.FORMATTING:
            return self.FORMATTING_MODELS
        elif task == TaskType.STANDARD:
            return self.DEFAULT_MODELS
        else:
            return self.DEFAULT_MODELS

    @staticmethod
    def get_provider_name(model_id: str) -> str:
        """Extract provider name from OpenRouter model ID."""
        if "/" in model_id:
            return model_id.split("/")[0]
        return "unknown"
