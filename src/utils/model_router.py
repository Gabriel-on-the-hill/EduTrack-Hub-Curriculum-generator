
from enum import Enum

class TaskType(str, Enum):
    """Types of tasks requiring different model capabilities."""
    REASONING = "reasoning"     # Complex logic, planning, evaluation (high IQ)
    CREATIVE = "creative"       # Content generation, prose, storytelling (high EQ)
    FORMATTING = "formatting"   # Structure, JSON/XML output, simple transforms (fast/cheap)
    STANDARD = "standard"       # General purpose default

class ModelRouter:
    """
    Stateless helper to prioritize available models based on task requirements.
    Uses keyword heuristics against the *verified* list of available models.
    """
    
    def prioritize_models(self, task: TaskType, available_models: list[str]) -> list[str]:
        """
        Sort and filter available models for the specific task.
        Returns a list of model IDs, best first.
        """
        if task == TaskType.REASONING:
            return self._filter_reasoning(available_models)
        elif task == TaskType.CREATIVE:
            return self._filter_creative(available_models)
        elif task == TaskType.FORMATTING:
            return self._filter_formatting(available_models)
        else:
            return available_models # Return all valid free models

    def _filter_reasoning(self, models: list[str]) -> list[str]:
        # Prioritize "thinking" or "reasoner" models
        # DeepSeek R1 is king, Gemini Flash Thinking is queen
        priority = []
        others = []
        for m in models:
            m_lower = m.lower()
            if "deepseek-r1" in m_lower or "thinking" in m_lower:
                priority.append(m)
            elif "claude-3-opus" in m_lower or "gemini-1.5-pro" in m_lower: # If free versions exist
                priority.append(m)
            else:
                others.append(m)
        return priority + others

    def _filter_creative(self, models: list[str]) -> list[str]:
        # Prioritize high-parameter or creative-tuned models
        priority = []
        others = []
        for m in models:
            m_lower = m.lower()
            if "70b" in m_lower or "mistral-large" in m_lower or "gemini-1.5-pro" in m_lower:
                priority.append(m)
            elif "mythomax" in m_lower or "liquid" in m_lower:
                others.append(m)
            else:
                others.append(m)
        return priority + others

    def _filter_formatting(self, models: list[str]) -> list[str]:
        # Prioritize fast, instruction-following models
        priority = []
        others = []
        for m in models:
            m_lower = m.lower()
            if "flash" in m_lower or "haiku" in m_lower or "8b" in m_lower:
                priority.append(m)
            else:
                others.append(m)
        return priority + others
