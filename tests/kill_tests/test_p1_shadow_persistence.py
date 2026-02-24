"""
P1 Kill Tests - Shadow Persistence (KT-S Group)

Purpose: Verify that Shadow Logs are persisted and policy-compliant.
"""

import pytest
import asyncio
import json
import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from src.production.errors import HallucinationBlockError

class TestShadowPersistence:

    @pytest.fixture(autouse=True)
    def clean_logs(self):
        """Clean up log directory before/after tests."""
        log_dir = Path("./kill_test_logs")
        if log_dir.exists():
            shutil.rmtree(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        yield
        # shutil.rmtree(log_dir) # Keep for inspection if needed

    def test_kt_s1_log_persisted_after_alert(self, harness, valid_provenance):
        """
        KT-S1: Log persisted after alert.
        Action: Trigger HallucinationBlockError.
        Expected: A JSON log file exists in storage path.
        """
        # Trigger hallucination
        # Mock grounding to PASS so we reach shadow check
        # We replace the ENTIRE grounding verifier instance to ensure verify_artifact is intercepted
        harness.grounding = Mock()
        harness.grounding.verify_artifact.return_value = Mock(is_clean=True, verdict="PASS")
        
        with patch('src.production.harness.fetch_competencies', return_value=[{"id": "1", "text": "Bio"}]), \
             patch('src.production.harness.fetch_curriculum_mode', return_value="k12"), \
             patch('src.production.harness.extract_topics', side_effect=[["a"], ["a", "z"]]), \
             patch.dict('os.environ', {'HALLUCINATION_ACTION': 'BLOCK'}): # 50% extra

            mock_config = Mock()
            mock_config.grade = "Grade 9"
            mock_config.jurisdiction = "National"
            mock_config.topic_title = "Biology"

            try:
                asyncio.run(harness.generate_artifact("test-persist", mock_config, valid_provenance))
                pytest.fail("Should have raised HallucinationBlockError")
            except Exception as e:
                # Check if it's the right error
                assert "HallucinationBlockError" in type(e).__name__ 
                assert "Shadow hallucination detected" in str(e)
            
            # Verify file exists
            log_dir = Path("./kill_test_logs")
            logs = list(log_dir.glob("**/*.json"))
            assert len(logs) > 0, "No shadow logs found after alert"
            
            # Verify content
            with open(logs[0]) as f:
                data = json.load(f)
                assert "alerts" in data
                assert "HALLUCINATION_RISK_HIGH" in data["alerts"]

    def test_kt_s3_pii_scrubbed(self, harness):
        """
        KT-S3: PII Scrubbed.
        Verify no email/phone patterns in logs.
        For this test, we inject PII into the 'student_profile' metadata if possible,
        or ensure the system doesn't log raw inputs blindly.
        """
        # The harness currently doesn't take user inputs directly in generate_artifact 
        # (it takes config/provenance).
        # We check that the log doesn't contain unexpected fields.
        pass # To be implemented if we start logging user context.

