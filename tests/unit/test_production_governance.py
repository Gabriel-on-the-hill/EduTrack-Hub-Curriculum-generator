"""
Unit Tests for Governance Enforcer (Phase 5)

Verifies provenance schema enforcement and university disclaimers.
"""

import pytest
from src.production.governance import GovernanceEnforcer, ProvenanceBlock
from src.synthetic.schemas import SyntheticCurriculumOutput

@pytest.fixture
def valid_provenance():
    return {
        "curriculum_id": "test-uuid",
        "source_list": [{
            "url": "http://uni.edu",
            "authority": "Test University",
            "fetch_date": "2026-02-02"
        }],
        "retrieval_timestamp": "2026-02-02T12:00:00",
        "replica_version": "v1.0",
        "extraction_confidence": 0.95
    }

@pytest.fixture
def enforcer():
    return GovernanceEnforcer(strict_mode=True)

def test_governance_enforces_provenance_schema(enforcer, valid_provenance):
    """Governance must accept valid provenance."""
    output = SyntheticCurriculumOutput(
        curriculum_id="test-uuid",
        content_markdown="Some content",
        metrics={}
    )
    
    result = enforcer.enforce(output, "National", valid_provenance)
    assert result.metadata["provenance_block"]["curriculum_id"] == "test-uuid"

def test_governance_rejects_missing_provenance(enforcer):
    """Governance must raise violation if provenance is missing."""
    output = SyntheticCurriculumOutput(curriculum_id="id", content_markdown="cx")
    
    with pytest.raises(ValueError, match="Governance Violation"):
        enforcer.enforce(output, "National", None)

def test_university_content_gets_disclaimer(enforcer, valid_provenance):
    """University content must have disclaimer injected."""
    output = SyntheticCurriculumOutput(
        curriculum_id="test-uuid",
        content_markdown="# Lecture 1\nContent."
    )
    
    result = enforcer.enforce(output, "Active University", valid_provenance)
    
    assert "DISCLAIMER" in result.content_markdown
    assert "Test University" in result.content_markdown
    assert result.content_markdown.startswith("> DISCLAIMER")

def test_university_low_confidence_flagged(enforcer, valid_provenance):
    """Low confidence university content is flagged."""
    valid_provenance["extraction_confidence"] = 0.80
    output = SyntheticCurriculumOutput(curriculum_id="id", content_markdown="c")
    
    result = enforcer.enforce(output, "Active University", valid_provenance)
    
    assert result.metadata["university_governance_applied"] is True
