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
    # Sentences containing "aligned" -> [1.0, 0.0] (grounded)
    # Sentences containing "unrelated" -> [0.0, 1.0] (not grounded)
    
    def fake_embed(texts):
        # Return simple 2D vectors
        # "aligned" -> [1.0, 0.0]
        # "unrelated" -> [0.0, 1.0]
        # Anything else defaults to [0.0, 1.0] (ungrounded)
        embeddings = []
        for t in texts:
            if "aligned" in t.lower():
                embeddings.append([1.0, 0.0])
            elif "unrelated" in t.lower():
                embeddings.append([0.0, 1.0])
            else:
                # Default: check if it looks like it should be grounded
                embeddings.append([0.0, 1.0])
        return embeddings
        
    provider.embed.side_effect = fake_embed
    provider.name.return_value = "mock_provider"
    return provider

def test_k12_fails_with_ungrounded_sentence(mock_embedding_provider):
    """K-12 must reject artifact if even ONE sentence is ungrounded."""
    verifier = GroundingVerifier(embedding_provider=mock_embedding_provider, similarity_threshold=0.85)
    
    competencies = [{"id": "c1", "text": "This is an aligned competency topic"}]
    # Use sentences > 10 chars so they pass the sentence splitter filter
    artifact_text = "This sentence is aligned with the topic. This sentence is unrelated to everything."
    
    report = verifier.verify_artifact(artifact_text, competencies, mode="k12")
    
    assert report.total_sentences == 2
    assert report.grounded_count == 1
    assert report.ungrounded_count == 1
    assert report.verdict == "FAIL"
    assert report.is_clean is False

def test_k12_passes_with_perfect_grounding(mock_embedding_provider):
    """K-12 passes only if ALL sentences are grounded."""
    verifier = GroundingVerifier(embedding_provider=mock_embedding_provider)
    
    competencies = [{"id": "c1", "text": "This is an aligned competency topic"}]
    artifact_text = "This sentence is aligned with the curriculum. Another aligned sentence here."
    
    report = verifier.verify_artifact(artifact_text, competencies, mode="k12")
    
    assert report.verdict == "PASS"
    assert report.is_clean is True

def test_university_allows_small_deviation(mock_embedding_provider):
    """University allows 5% ungrounded."""
    verifier = GroundingVerifier(embedding_provider=mock_embedding_provider)
    
    competencies = [{"id": "c1", "text": "This is an aligned competency topic"}]
    
    # 20 sentences: 19 aligned, 1 unrelated = 95% rate -> PASS
    aligned_sentences = [f"Sentence number {i} is aligned with the curriculum" for i in range(19)]
    unrelated_sentences = ["This sentence is unrelated to anything"]
    artifact_text = ". ".join(aligned_sentences + unrelated_sentences) + "."
    
    report = verifier.verify_artifact(artifact_text, competencies, mode="university")
    
    assert report.total_sentences == 20
    assert report.grounded_count == 19
    assert report.ungrounded_count == 1
    assert report.grounding_rate == 0.95
    assert report.verdict == "PASS"  # 0.95 is valid for Uni

def test_university_rejects_large_deviation(mock_embedding_provider):
    """University rejects >5% ungrounded."""
    verifier = GroundingVerifier(embedding_provider=mock_embedding_provider)
    
    competencies = [{"id": "c1", "text": "This is an aligned competency topic"}]
    
    # 20 sentences: 18 aligned, 2 unrelated = 90% rate -> FAIL
    aligned_sentences = [f"Sentence number {i} is aligned with the curriculum" for i in range(18)]
    unrelated_sentences = [
        "This sentence is unrelated to anything",
        "Another unrelated sentence appears here"
    ]
    artifact_text = ". ".join(aligned_sentences + unrelated_sentences) + "."
    
    report = verifier.verify_artifact(artifact_text, competencies, mode="university")
    
    assert report.grounding_rate == 0.90
    assert report.verdict == "FAIL"
