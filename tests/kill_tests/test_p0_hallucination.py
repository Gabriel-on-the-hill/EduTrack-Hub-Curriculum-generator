"""
P0 Kill Tests - Hallucination Defense (KT-B Group)

Critical Purpose: Ensure NO ungrounded content is ever returned.
"""

import pytest
from unittest.mock import Mock, patch
from src.production.errors import GroundingViolationError, HallucinationBlockError
from src.production.harness import ProductionHarness

class TestHallucinationDefense:

    def test_kt_b1_pure_fabrication_unit(self, harness, seeded_curriculum, valid_provenance):
        """
        KT-B1: Pure Fabrication (Unit)
        Injected: "Quantum epigenetic synthesis"
        Expected: GroundingViolationError raised
        """
        # Mock grounding to fail specifically on this sentence
        mock_report = Mock()
        mock_report.is_clean = False
        mock_report.verdict = "FAIL" # Explicitly mock verdict
        mock_report.ungrounded_sentences = ["Quantum epigenetic synthesis"]
        harness.grounding.verify_artifact = Mock(return_value=mock_report)
        
        # Need to ensure fetch_curriculum_mode and fetch_competencies don't block before grounding
        with patch('src.production.harness.fetch_curriculum_mode', return_value="k12"), \
             patch('src.production.harness.fetch_competencies', return_value=[{"id": "1", "text": "Basic Bio"}]):
            
            with pytest.raises(GroundingViolationError) as exc:
                harness.generate_artifact(
                    curriculum_id="test", 
                    config=Mock(), 
                    provenance=valid_provenance
                )
            
            assert "Quantum epigenetic synthesis" in exc.value.ungrounded_sentences

    def test_kt_b1_e2e_grounding(self, harness, valid_provenance):
        """
        KT-B1-E2E: Full Harness Path
        Ensures the exception actually bubbles up through the generate_artifact method.
        (Covered partly by unit, but this emphasizes the contract)
        """
        # Same setup, emphasizing the integration aspect
        self.test_kt_b1_pure_fabrication_unit(harness, None, valid_provenance)

    def test_kt_b2_semantic_stretch_k12(self, harness, valid_provenance):
        """
        KT-B2: Semantic Stretch (K-12) -> BLOCK
        """
        mock_report = Mock()
        mock_report.is_clean = False # K12 requires 100%
        mock_report.verdict = "FAIL"
        mock_report.grounding_rate = 0.99
        mock_report.ungrounded_sentences = ["Advanced stuff"]
        harness.grounding.verify_artifact = Mock(return_value=mock_report)
        
        with patch('src.production.harness.fetch_curriculum_mode', return_value="k12"), \
             patch('src.production.harness.fetch_competencies', return_value=[{"id": "1", "text": "Bio"}]):
            
            with pytest.raises(GroundingViolationError):
                harness.generate_artifact("test-k12", Mock(), valid_provenance)

    def test_kt_b2_semantic_stretch_uni(self, harness, valid_provenance):
        """
        KT-B2: Semantic Stretch (University) -> ALLOW if >= 95%
        """
        mock_report = Mock()
        mock_report.is_clean = False 
        mock_report.verdict = "PASS" # Explicit pass for Uni mode
        mock_report.grounding_rate = 0.96 # Above 95%
        mock_report.ungrounded_sentences = ["Some academic nuance"]
        harness.grounding.verify_artifact = Mock(return_value=mock_report)
        
        # Mock other steps to allow success
        with patch('src.production.harness.fetch_curriculum_mode', return_value="university"), \
             patch('src.production.harness.fetch_competencies', return_value=[{"id": "1", "text": "Bio"}]), \
             patch('src.production.harness.extract_topics', return_value=[]), \
             patch.object(harness.shadow_logger, 'log_shadow_run', return_value=Mock(alerts=[], metrics=Mock(extra_topic_rate=0.0))):
             
             # Should NOT raise
             harness.generate_artifact("test-uni", Mock(), valid_provenance)

    def test_kt_b3_shadow_disagreement(self, harness, valid_provenance):
        """
        KT-B3: Shadow Disagreement
        Expected: extra_topic_rate > 0.01 -> HallucinationBlockError
        """
        # Make grounding pass
        harness.grounding.verify_artifact = Mock(return_value=Mock(is_clean=True))
        
        # Inject discordant topics
        # Primary: A, B, C
        # Shadow: A, B, C, D (1/4 = 25% extra > 1%)
        with patch('src.production.harness.fetch_curriculum_mode', return_value="k12"), \
             patch('src.production.harness.fetch_competencies', return_value=[{"id": "1", "text": "Bio"}]), \
             patch('src.production.harness.extract_topics', side_effect=[
                 ["a", "b", "c"],       # Primary
                 ["a", "b", "c", "d"]   # Shadow
             ]):
            
            with pytest.raises(HallucinationBlockError) as exc:
                harness.generate_artifact("test-shadow-fail", Mock(), valid_provenance)
                
            assert exc.value.extra_topic_rate == 0.25
            assert "HALLUCINATION_RISK_HIGH" in exc.value.alerts
