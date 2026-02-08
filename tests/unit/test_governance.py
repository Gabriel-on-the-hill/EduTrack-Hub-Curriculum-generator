"""
Unit tests for university curriculum governance.

Tests disclaimer generation, provenance metadata, and governance decisions.
"""

from datetime import date, timedelta

import pytest

from src.schemas.base import CurriculumMode, InstitutionType
from src.synthetic.governance import (
    DisclaimerLevel,
    DisclaimerGenerator,
    ProvenanceMetadata,
    GovernanceDecision,
    UniversityConfidenceThresholds,
    evaluate_governance,
)


class TestUniversityConfidenceThresholds:
    """Tests for confidence threshold differences."""
    
    def test_k12_higher_thresholds(self):
        """K-12 has higher confidence thresholds."""
        k12_source = UniversityConfidenceThresholds.K12_SOURCE_VALIDATION
        uni_source = UniversityConfidenceThresholds.UNIVERSITY_SOURCE_VALIDATION
        
        assert k12_source > uni_source
        assert k12_source == 0.90
        assert uni_source == 0.75
    
    def test_get_threshold_by_mode(self):
        """Get appropriate threshold by mode."""
        k12_thresh = UniversityConfidenceThresholds.get_threshold(
            CurriculumMode.K12, "source_validation"
        )
        uni_thresh = UniversityConfidenceThresholds.get_threshold(
            CurriculumMode.SYLLABUS, "source_validation"
        )
        
        assert k12_thresh == 0.90
        assert uni_thresh == 0.75


class TestDisclaimerGenerator:
    """Tests for disclaimer generation."""
    
    def test_k12_no_disclaimer(self):
        """K-12 content has no disclaimer."""
        disclaimer = DisclaimerGenerator.generate(CurriculumMode.K12)
        assert disclaimer is None
    
    def test_accredited_university_standard_disclaimer(self):
        """Accredited university gets standard disclaimer."""
        disclaimer = DisclaimerGenerator.generate(
            CurriculumMode.SYLLABUS,
            InstitutionType.ACCREDITED
        )
        assert disclaimer is not None
        assert "syllabus" in disclaimer.lower()
        assert "verify" in disclaimer.lower()
    
    def test_unknown_institution_enhanced_disclaimer(self):
        """Unknown institution gets enhanced disclaimer."""
        disclaimer = DisclaimerGenerator.generate(
            CurriculumMode.SYLLABUS,
            InstitutionType.UNKNOWN
        )
        assert disclaimer is not None
        assert "⚠️" in disclaimer  # Warning symbol
        assert "not be relied upon" in disclaimer
    
    def test_training_provider_maximum_disclaimer(self):
        """Training provider gets maximum disclaimer."""
        disclaimer = DisclaimerGenerator.generate(
            CurriculumMode.SYLLABUS,
            InstitutionType.TRAINING_PROVIDER
        )
        assert disclaimer is not None
        assert "UNVERIFIED SOURCE" in disclaimer
        assert "at your own risk" in disclaimer.lower()
    
    def test_custom_disclaimer_override(self):
        """Custom disclaimer overrides default."""
        custom = "Custom disclaimer text"
        disclaimer = DisclaimerGenerator.generate(
            CurriculumMode.SYLLABUS,
            InstitutionType.ACCREDITED,
            custom_disclaimer=custom
        )
        assert disclaimer == custom
    
    def test_disclaimer_level_determination(self):
        """Correct disclaimer level determined."""
        assert DisclaimerGenerator.determine_level(
            CurriculumMode.K12
        ) == DisclaimerLevel.NONE
        
        assert DisclaimerGenerator.determine_level(
            CurriculumMode.SYLLABUS, InstitutionType.ACCREDITED
        ) == DisclaimerLevel.STANDARD
        
        assert DisclaimerGenerator.determine_level(
            CurriculumMode.SYLLABUS, InstitutionType.UNKNOWN
        ) == DisclaimerLevel.ENHANCED


class TestProvenanceMetadata:
    """Tests for provenance metadata."""
    
    def test_age_days_calculation(self):
        """Age calculated correctly."""
        provenance = ProvenanceMetadata(
            source_url="https://example.edu/syllabus.pdf",
            source_domain="example.edu",
            extraction_date=date.today() - timedelta(days=45),
            extraction_confidence=0.85,
            curriculum_mode=CurriculumMode.SYLLABUS,
        )
        assert provenance.age_days == 45
    
    def test_staleness_levels(self):
        """Staleness levels assigned correctly."""
        # Fresh (< 30 days)
        fresh = ProvenanceMetadata(
            source_url="https://example.edu/syllabus.pdf",
            source_domain="example.edu",
            extraction_date=date.today() - timedelta(days=10),
            extraction_confidence=0.85,
            curriculum_mode=CurriculumMode.SYLLABUS,
        )
        assert fresh.staleness_level == "fresh"
        
        # Aging (30-60 days)
        aging = ProvenanceMetadata(
            source_url="https://example.edu/syllabus.pdf",
            source_domain="example.edu",
            extraction_date=date.today() - timedelta(days=45),
            extraction_confidence=0.85,
            curriculum_mode=CurriculumMode.SYLLABUS,
        )
        assert aging.staleness_level == "aging"
        
        # Stale (60-120 days)
        stale = ProvenanceMetadata(
            source_url="https://example.edu/syllabus.pdf",
            source_domain="example.edu",
            extraction_date=date.today() - timedelta(days=100),
            extraction_confidence=0.85,
            curriculum_mode=CurriculumMode.SYLLABUS,
        )
        assert stale.staleness_level == "stale"
        
        # Expired (> 120 days)
        expired = ProvenanceMetadata(
            source_url="https://example.edu/syllabus.pdf",
            source_domain="example.edu",
            extraction_date=date.today() - timedelta(days=150),
            extraction_confidence=0.85,
            curriculum_mode=CurriculumMode.SYLLABUS,
        )
        assert expired.staleness_level == "expired"
    
    def test_format_provenance(self):
        """Provenance formats correctly."""
        provenance = ProvenanceMetadata(
            source_url="https://mit.edu/course.pdf",
            source_domain="mit.edu",
            extraction_date=date.today(),
            extraction_confidence=0.85,
            curriculum_mode=CurriculumMode.SYLLABUS,
            institution_name="MIT",
            course_code="6.001",
        )
        formatted = provenance.format_provenance()
        assert "MIT" in formatted
        assert "6.001" in formatted
        assert "85%" in formatted


class TestGovernanceDecision:
    """Tests for governance decision evaluation."""
    
    def test_k12_simple_approval(self):
        """K-12 content gets simple approval."""
        decision = evaluate_governance(CurriculumMode.K12)
        
        assert decision.allow_output is True
        assert decision.disclaimer_level == DisclaimerLevel.NONE
        assert decision.disclaimer_text is None
        assert decision.requires_provenance is False
    
    def test_university_requires_provenance(self):
        """University content requires provenance."""
        decision = evaluate_governance(
            CurriculumMode.SYLLABUS,
            institution_type=InstitutionType.ACCREDITED
        )
        
        assert decision.allow_output is True
        assert decision.requires_provenance is True
        assert decision.disclaimer_text is not None
    
    def test_stale_content_warning(self):
        """Stale content gets warning and confidence adjustment."""
        stale_provenance = ProvenanceMetadata(
            source_url="https://example.edu/old.pdf",
            source_domain="example.edu",
            extraction_date=date.today() - timedelta(days=100),
            extraction_confidence=0.85,
            curriculum_mode=CurriculumMode.SYLLABUS,
        )
        
        decision = evaluate_governance(
            CurriculumMode.SYLLABUS,
            provenance=stale_provenance,
            institution_type=InstitutionType.ACCREDITED
        )
        
        assert decision.staleness_warning is not None
        assert "100 days" in decision.staleness_warning
        assert decision.confidence_adjustment < 0
    
    def test_training_provider_blocks_production(self):
        """Training provider blocks production deployment."""
        decision = evaluate_governance(
            CurriculumMode.SYLLABUS,
            institution_type=InstitutionType.TRAINING_PROVIDER
        )
        
        assert decision.blocks_production is True
        assert decision.disclaimer_level == DisclaimerLevel.MAXIMUM
