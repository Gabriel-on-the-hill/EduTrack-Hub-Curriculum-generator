"""
Standard Unittest Runner for Production Modules.
Bypasses pytest dependency issues.
"""
import unittest
import sys
import os
from unittest.mock import Mock, MagicMock

# Add src to path
sys.path.append(os.getcwd())

from sqlalchemy import Column, Integer, String, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from src.production.security import ReadOnlySession
from src.production.grounding import GroundingVerifier, GroundingCheckResult
from src.production.governance import GovernanceEnforcer, ProvenanceBlock
from src.synthetic.schemas import SyntheticCurriculumOutput

# =============================================================================
# SECURITY TESTS
# =============================================================================

Base = declarative_base()

class MockModel(Base):
    __tablename__ = "mock_items_std"
    id = Column(Integer, primary_key=True)
    name = Column(String)

class TestSecurity(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def test_readonly_session_blocks_insert(self):
        Session = sessionmaker(bind=self.engine, class_=ReadOnlySession)
        session = Session()
        item = MockModel(name="forbidden")
        session.add(item)
        
        with self.assertRaises(PermissionError) as cm:
            session.flush()
        self.assertIn("Generate-Safety Violation", str(cm.exception))

# =============================================================================
# GROUNDING TESTS (Fixed sentence length)
# =============================================================================

class TestGrounding(unittest.TestCase):
    def setUp(self):
        self.mock_provider = Mock()
        def fake_embed(texts):
            embeddings = []
            for t in texts:
                # Critical: Check mismatch first because "mismatch" contains "match"
                if "mismatch" in t:
                    embeddings.append([0.0, 1.0])
                elif "match" in t:
                    embeddings.append([1.0, 0.0])
                elif "partial" in t:
                    embeddings.append([0.707, 0.707]) 
                else:
                    embeddings.append([0.0, 1.0])
            return embeddings
        self.mock_provider.embed.side_effect = fake_embed

    def test_k12_fails_with_ungrounded(self):
        verifier = GroundingVerifier(embedding_provider=self.mock_provider, similarity_threshold=0.85)
        competencies = [{"id": "c1", "text": "match this competency"}]
        # Sentences must be > 10 chars to survive filter
        # 1 match, 1 mismatch
        sentence_1 = "This is a simple matching sentence."
        sentence_2 = "This is a mismatching sentence."
        text = f"{sentence_1} {sentence_2}"
        
        report = verifier.verify_artifact(text, competencies, mode="k12")
        
        self.assertEqual(report.total_sentences, 2)
        self.assertEqual(report.grounded_count, 1)
        self.assertEqual(report.verdict, "FAIL")
        self.assertFalse(report.is_clean)

    def test_university_allows_5_percent(self):
        verifier = GroundingVerifier(embedding_provider=self.mock_provider)
        competencies = [{"id": "c1", "text": "match this competency"}]
        
        # 19 matches, 1 mismatch = 95%
        # Use long sentences
        match_sent = "This is a simple matching sentence."
        mismatch_sent = "This is a mismatching sentence."
        
        sentences = [match_sent] * 19 + [mismatch_sent]
        text = ". ".join(sentences) + "."
        
        report = verifier.verify_artifact(text, competencies, mode="university")
        
        self.assertEqual(report.total_sentences, 20)
        self.assertEqual(report.grounding_rate, 0.95)
        self.assertEqual(report.verdict, "PASS")

# =============================================================================
# GOVERNANCE TESTS
# =============================================================================

class TestGovernance(unittest.TestCase):
    def setUp(self):
        self.enforcer = GovernanceEnforcer(strict_mode=True)
        self.provenance = {
            "curriculum_id": "test",
            "source_list": [{"url": "http://u", "authority": "Uni", "fetch_date": "2026-02-02"}],
            "retrieval_timestamp": "2026-02-02",
            "replica_version": "v1",
            "extraction_confidence": 0.95
        }

    def test_provenance_schema_valid(self):
        output = SyntheticCurriculumOutput.model_construct(
            curriculum_id="id", 
            content_markdown="c",
            metrics={},
            metadata={}
        )
        res = self.enforcer.enforce(output, "National", self.provenance)
        self.assertEqual(res.metadata["provenance_block"]["source_list"][0]["authority"], "Uni")

    def test_university_disclaimer(self):
        output = SyntheticCurriculumOutput.model_construct(
            curriculum_id="id", 
            content_markdown="data",
            metrics={},
            metadata={}
        )
        res = self.enforcer.enforce(output, "Active University", self.provenance)
        self.assertIn("DISCLAIMER", res.content_markdown)

# =============================================================================
# SHADOW LOGGING TESTS
# =============================================================================

from src.production.shadow import ShadowDeltaLogger

class TestShadowLogging(unittest.TestCase):
    def setUp(self):
        self.logger = ShadowDeltaLogger()

    def test_topic_set_delta_calculation(self):
        # Intersection 2, Union 4. Jaccard 0.5. Delta 0.5.
        primary = ["a", "b", "c"]
        shadow = ["b", "c", "d"]
        metrics, alerts = self.logger.compute_metrics(primary, shadow)
        self.assertEqual(metrics.topic_set_delta, 0.5)

    def test_kendall_tau_reversal(self):
        # Reverse order = 1.0 delta
        primary = ["a", "b", "c"]
        shadow = ["c", "b", "a"]
        metrics, alerts = self.logger.compute_metrics(primary, shadow)
        self.assertEqual(metrics.ordering_delta, 1.0)
        self.assertIn("ORDERING_DELTA_HIGH", alerts) # > 0.20

    def test_kendall_tau_identical(self):
        # Identical order = 0.0 delta
        primary = ["a", "b"]
        shadow = ["a", "b"]
        metrics, alerts = self.logger.compute_metrics(primary, shadow)
        self.assertEqual(metrics.ordering_delta, 0.0)

    def test_hallucination_alert(self):
        # Shadow has extra topic "z". Rate = 1/4 = 0.25 > 0.01 threshold
        primary = ["a", "b", "c"]
        shadow = ["a", "b", "c", "z"]
        metrics, alerts = self.logger.compute_metrics(primary, shadow)
        self.assertIn("HALLUCINATION_RISK_HIGH", alerts)
        self.assertEqual(metrics.extra_topic_rate, 0.25)

if __name__ == "__main__":
    unittest.main()
