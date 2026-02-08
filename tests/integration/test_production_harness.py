"""
Integration Tests for Production Harness (Phase 5 Blocking Fix 10)

Tests end-to-end behavior:
- Grounding rejection (not just warning)
- Shadow hallucination blocking
- Content delta computation
- Log persistence

Updated for new modular architecture.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add src to path
import sys
sys.path.insert(0, os.getcwd())

from src.production.harness import ProductionHarness, ModelProvenance
from src.production.errors import GroundingViolationError, HallucinationBlockError
from src.production.shadow import ShadowDeltaLogger
from src.production.security import ReadOnlySession
from src.synthetic.schemas import SyntheticCurriculumOutput


class MockReadOnlySession:
    """Mock session that passes verify_readonly_status."""
    pass


class TestHarnessRejectsUngroundedEndToEnd(unittest.TestCase):
    """Fix 10: test_harness_rejects_ungrounded_end_to_end"""
    
    def setUp(self):
        # Patch verify_readonly_status to accept our mock
        self.verify_patch = patch('src.production.harness.verify_readonly_status', return_value=True)
        self.verify_db_patch = patch('src.production.harness.verify_db_is_readonly', return_value=True)
        self.mode_patch = patch('src.production.harness.fetch_curriculum_mode', return_value="k12")
        self.competencies_patch = patch('src.production.harness.fetch_competencies', return_value=[{"id": "c1", "text": "Test"}])
        
        self.verify_patch.start()
        self.verify_db_patch.start()
        self.mode_patch.start()
        self.competencies_patch.start()
        
        # Create harness with mock session
        self.harness = ProductionHarness(
            db_session=MockReadOnlySession(),
            primary_provenance=ModelProvenance(model_id="test-primary"),
            shadow_provenance=ModelProvenance(model_id="test-shadow"),
            verify_db_level=False
        )
        
        # Mock grounding to return failure
        self.mock_report = Mock()
        self.mock_report.is_clean = False
        self.mock_report.grounding_rate = 0.50
        self.mock_report.ungrounded_sentences = ["Ungrounded sentence 1", "Ungrounded sentence 2"]
        
        self.harness.grounding.verify_artifact = Mock(return_value=self.mock_report)
        
    def tearDown(self):
        self.verify_patch.stop()
        self.verify_db_patch.stop()
        self.mode_patch.stop()
        self.competencies_patch.stop()
    
    def test_k12_rejects_ungrounded_artifact(self):
        """K-12 mode must raise GroundingViolationError for ungrounded content."""
        provenance = {
            "curriculum_id": "test",
            "source_list": [{"url": "http://test", "authority": "Test", "fetch_date": "2026"}],
            "retrieval_timestamp": "2026",
            "extraction_confidence": 0.95
        }
        
        with self.assertRaises(GroundingViolationError) as ctx:
            self.harness.generate_artifact(
                curriculum_id="test-id",
                config=Mock(),
                provenance=provenance
            )
        
        self.assertIn("ungrounded content", str(ctx.exception))


class TestShadowBlockerTriggersAndPersistsAlert(unittest.TestCase):
    """Fix 10: test_shadow_blocker_triggers_and_persists_alert"""
    
    def setUp(self):
        self.verify_patch = patch('src.production.harness.verify_readonly_status', return_value=True)
        self.verify_db_patch = patch('src.production.harness.verify_db_is_readonly', return_value=True)
        self.mode_patch = patch('src.production.harness.fetch_curriculum_mode', return_value="k12")
        self.competencies_patch = patch('src.production.harness.fetch_competencies', return_value=[{"id": "c1", "text": "Test"}])
        
        self.verify_patch.start()
        self.verify_db_patch.start()
        self.mode_patch.start()
        self.competencies_patch.start()
        
        self.harness = ProductionHarness(
            db_session=MockReadOnlySession(),
            verify_db_level=False
        )
        
        # Make grounding pass
        mock_report = Mock()
        mock_report.is_clean = True
        mock_report.grounding_rate = 1.0
        self.harness.grounding.verify_artifact = Mock(return_value=mock_report)
        
        # Mock topic extraction to return divergent topics via extract_topics
        self.extract_patch = patch('src.production.harness.extract_topics')
        mock_extract = self.extract_patch.start()
        mock_extract.side_effect = [
            ["topic a", "topic b"],  # Primary
            ["topic a", "topic b", "topic c", "topic d", "topic e"]  # Shadow (3 extra = 60%)
        ]
        
    def tearDown(self):
        self.verify_patch.stop()
        self.verify_db_patch.stop()
        self.mode_patch.stop()
        self.competencies_patch.stop()
        self.extract_patch.stop()
        
    def test_hallucination_blocks_request(self):
        """Extra topic rate > 1% must raise HallucinationBlockError."""
        provenance = {
            "curriculum_id": "test",
            "source_list": [{"url": "http://test", "authority": "Test", "fetch_date": "2026"}],
            "retrieval_timestamp": "2026",
            "extraction_confidence": 0.95
        }
        
        with self.assertRaises(HallucinationBlockError) as ctx:
            self.harness.generate_artifact(
                curriculum_id="test-id",
                config=Mock(),
                provenance=provenance
            )
        
        self.assertIn("HALLUCINATION_RISK_HIGH", ctx.exception.alerts)


class TestContentDeltaCalculationWithEmbedding(unittest.TestCase):
    """Fix 10: test_content_delta_calculation_with_embedding"""
    
    def setUp(self):
        # Create mock embedding provider
        self.mock_provider = Mock()
        self.mock_provider.model_name = "test-embedding-model"
        
        self.temp_dir = tempfile.mkdtemp()
        
        self.logger = ShadowDeltaLogger(
            embedding_provider=self.mock_provider,
            storage_path=self.temp_dir
        )
        
    def test_content_delta_computed_with_embeddings(self):
        """Content delta must use embedding cosine similarity."""
        # Orthogonal vectors = 0 similarity = 1.0 delta
        self.mock_provider.embed = Mock(return_value=[
            [1.0, 0.0, 0.0],  # Primary
            [0.0, 1.0, 0.0]   # Shadow (orthogonal)
        ])
        
        metrics, alerts = self.logger.compute_metrics(
            primary_topics=["A"],
            shadow_topics=["A"],
            primary_content="Primary text",
            shadow_content="Shadow text"
        )
        
        # Orthogonal vectors should give delta close to 1.0
        self.assertAlmostEqual(metrics.content_delta, 1.0, places=2)
        self.assertIn("CONTENT_DELTA_HIGH", alerts)
        
    def test_identical_content_has_zero_delta(self):
        """Identical embeddings should have 0 delta."""
        self.mock_provider.embed = Mock(return_value=[
            [1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0]  # Identical
        ])
        
        metrics, _ = self.logger.compute_metrics(
            primary_topics=["A"],
            shadow_topics=["A"],
            primary_content="Same",
            shadow_content="Same"
        )
        
        self.assertAlmostEqual(metrics.content_delta, 0.0, places=4)


class TestShadowLogPersistence(unittest.TestCase):
    """Fix 5: Verify shadow logs are persisted."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.logger = ShadowDeltaLogger(storage_path=self.temp_dir)
        
    def test_log_persisted_to_storage(self):
        """Shadow log must be written to storage path."""
        primary = SyntheticCurriculumOutput.model_construct(
            curriculum_id="test",
            content_markdown="# Test",
            metadata={},
            metrics={}
        )
        shadow = SyntheticCurriculumOutput.model_construct(
            curriculum_id="test",
            content_markdown="# Test",
            metadata={},
            metrics={}
        )
        
        log = self.logger.log_shadow_run(
            job_id="job-123",
            request_id="req-456",
            curriculum_id="cur-789",
            primary_out=primary,
            shadow_out=shadow,
            primary_topics=["A"],
            shadow_topics=["A"]
        )
        
        # Verify file exists
        self.assertIsNotNone(log.storage_path)
        self.assertTrue(Path(log.storage_path).exists())
        
        # Verify JSON content
        import json
        with open(log.storage_path) as f:
            data = json.load(f)
        self.assertEqual(data["job_id"], "job-123")


if __name__ == "__main__":
    unittest.main()
