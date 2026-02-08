"""
Unit Tests for Grounding Verifier (Phase 5)

Verifies that GroundingVerifier strictly enforces 100% grounding for K-12
and 95% for University.
"""

import pytest
from unittest.mock import Mock, MagicMock
from src.production.grounding import GroundingVerifier, GroundingCheckResult

@pytest.fixture
def mock_embedding_provider():
    """Mock embedding provider to control similarities."""
    provider = Mock()
    # Mock behavior: return predictable embeddings
    # If text == source_text, dot product should be 1.0 (after normalization)
    
    def fake_embed(texts):
        # Return simple 2D vectors
        # "match" -> [1.0, 0.0]
        # "mismatch" -> [0.0, 1.0]
        embeddings = []
        for t in texts:
            if "match" in t:
                embeddings.append([1.0, 0.0])
            elif "partial" in t:
                embeddings.append([0.707, 0.707]) # 45 deg, cos=0.707
            else:
                embeddings.append([0.0, 1.0])
        return embeddings
        
    provider.embed.side_effect = fake_embed
    return provider

def test_k12_fails_with_ungrounded_sentence(mock_embedding_provider):
    """K-12 must reject artifact if even ONE sentence is ungrounded."""
    verifier = GroundingVerifier(embedding_provider=mock_embedding_provider, similarity_threshold=0.85)
    
    competencies = [{"id": "c1", "text": "match this competency"}]
    artifact_text = "This should match. This is mismatch."
    
    report = verifier.verify_artifact(artifact_text, competencies, mode="k12")
    
    assert report.total_sentences == 2
    assert report.grounded_count == 1
    assert report.ungrounded_count == 1
    assert report.verdict == "FAIL"
    assert report.is_clean is False

def test_k12_passes_with_perfect_grounding(mock_embedding_provider):
    """K-12 passes only if ALL sentences are grounded."""
    verifier = GroundingVerifier(embedding_provider=mock_embedding_provider)
    
    competencies = [{"id": "c1", "text": "match this competency"}]
    artifact_text = "This should match. match match."
    
    report = verifier.verify_artifact(artifact_text, competencies, mode="k12")
    
    assert report.verdict == "PASS"
    assert report.is_clean is True

def test_university_allows_small_deviation(mock_embedding_provider):
    """University allows 5% ungrounded."""
    verifier = GroundingVerifier(embedding_provider=mock_embedding_provider)
    
    competencies = [{"id": "c1", "text": "match this competency"}]
    
    # 20 sentences: 19 matches, 1 mismatch = 95% rate -> PASS
    sentences = ["match"] * 19 + ["mismatch"]
    artifact_text = ". ".join(sentences) + "."
    
    report = verifier.verify_artifact(artifact_text, competencies, mode="university")
    
    assert report.total_sentences == 20
    assert report.grounded_count == 19
    assert report.ungrounded_count == 1
    assert report.grounding_rate == 0.95
    assert report.verdict == "PASS" # 0.95 is valid for Uni

def test_university_rejects_large_deviation(mock_embedding_provider):
    """University rejects >5% ungrounded."""
    verifier = GroundingVerifier(embedding_provider=mock_embedding_provider)
    
    competencies = [{"id": "c1", "text": "match this competency"}]
    
    # 20 sentences: 18 matches, 2 mismatch = 90% rate -> FAIL
    sentences = ["match"] * 18 + ["mismatch", "mismatch"]
    artifact_text = ". ".join(sentences) + "."
    
    report = verifier.verify_artifact(artifact_text, competencies, mode="university")
    
    assert report.grounding_rate == 0.90
    assert report.verdict == "FAIL"
