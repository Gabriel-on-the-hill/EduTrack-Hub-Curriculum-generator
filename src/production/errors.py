"""
Production Errors (Phase 5)

Custom exceptions for strict enforcement.
"""


class GroundingViolationError(RuntimeError):
    """
    Raised when artifact fails grounding verification.
    This is a BLOCKER - no warnings, no TODOs.
    """
    def __init__(self, ungrounded_sentences: list[str]):
        super().__init__("Grounding violation: ungrounded content detected")
        self.ungrounded_sentences = ungrounded_sentences


class HallucinationBlockError(RuntimeError):
    """
    Raised when shadow execution detects hallucination risk.
    Silent logging ≠ safety. This makes it real.
    """
    def __init__(self, extra_topic_rate: float, alerts: list[str], request_id: str):
        super().__init__(f"Shadow hallucination detected for request {request_id}")
        self.extra_topic_rate = extra_topic_rate
        self.alerts = alerts
        self.request_id = request_id


class CompetencyNotFoundError(RuntimeError):
    """Raised when no competencies exist for a curriculum."""
    def __init__(self, curriculum_id: str):
        super().__init__(f"No competencies found for {curriculum_id}")
        self.curriculum_id = curriculum_id


class DatabaseNotReadOnlyError(PermissionError):
    """Raised when database is not properly configured as read-only."""
    def __init__(self):
        super().__init__("Database is not read-only - write operations are permitted")
