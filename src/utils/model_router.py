
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
    """
    
    # Priority lists for different task types (best to worst)
    # Using OpenRouter model IDs
    
    REASONING_MODELS = [
        "deepseek/deepseek-r1:free",             # State-of-the-art reasoning (when available)
        "google/gemini-2.0-flash-thinking-exp:free", # Fast reasoning
        "google/gemini-2.0-flash-001",           # Strong generalist
        "meta-llama/llama-3.3-70b-instruct:free",# Good fallback
    ]
    
    CREATIVE_MODELS = [
        "meta-llama/llama-3.3-70b-instruct:free", # Excellent prose
        "mistralai/mistral-small-24b-instruct-2501:free", # Good creative style
        "google/gemma-3-27b-it:free",            # Strong creative
        "microsoft/phi-4:free",                  # Good coherence
    ]
    
    FORMATTING_MODELS = [
        "meta-llama/llama-3-8b-instruct:free",   # Fast & strict instruction following
        "google/gemma-2-9b-it:free",             # Reliable formatting
        "mistralai/mistral-7b-instruct:free",    # Good for structured output
        "openrouter/auto",                       # Fallback to auto-router
    ]
    
    DEFAULT_MODELS = CREATIVE_MODELS

    def get_candidate_models(self, task: TaskType | str) -> list[str]:
        """
        Get a list of candidate models for a specific task, ordered by preference.
        
        Args:
            task: TaskType enum or string ("reasoning", "creative", "formatting")
            
        Returns:
            List of model IDs strings
        """
        if isinstance(task, str):
            try:
                task = TaskType(task.lower())
            except ValueError:
                # If unknown task string, log warning and use standard
                # For now just raise error to be strict as per TDD
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
        """
        Extract provider name from OpenRouter model ID.
        e.g. "google/gemini-pro" -> "google"
        """
        if "/" in model_id:
            return model_id.split("/")[0]
        return "unknown"
