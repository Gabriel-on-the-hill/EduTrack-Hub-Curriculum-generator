"""
Kill Test Thresholds Configuration (Phase 6)

Explicit, strict thresholds for the Kill Test Suite.
These values define the boundary between "Safe" and "Block".
"""

# Risk Thresholds
THRESHOLDS = {
    "extra_topic_rate": 0.01,       # BLOCK + Persist + Incident
    "extra_topic_rate_interim": 0.005, # Lower threshold until C1 fixed (Phase 6.2)
    "topic_set_delta": 0.05,        # Alert
    "ordering_delta": 0.20,         # Alert (non-blocking)
    "content_delta": 0.15,          # Alert; block if extra_topic > 0.005
    "omission_rate": 0.02,          # Alert; block on core topics
}

# SLA Targets (in milliseconds)
# P95 targets. Shadow mode roughly doubles these (shadow_multiplier).
SLA_THRESHOLDS = {
    "formatting_only": 300,
    "lesson_plan_short": 2000,
    "quiz_assessment": 5000,
    "shadow_multiplier": 2.0,
}

# Governance Constants
GOVERNANCE = {
    "university_grounding_threshold": 0.95,
    "k12_grounding_threshold": 1.00,
    "provenance_max_age_days": 365 * 2, # 2 years
}
