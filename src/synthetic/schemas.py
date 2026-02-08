"""
Synthetic Curriculum Schemas (Blueprint Section 22)

Defines the data models for synthetic curriculum generation and testing.
These are used to create controlled test fixtures for pipeline validation.
"""

from datetime import date
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class TopicWeight(str, Enum):
    """
    Topic weight classification for semantic omission severity.
    
    Blueprint Phase 4.1: Not all topic losses are equal.
    Core concepts must be protected more strictly.
    """
    FOUNDATIONAL = "foundational"  # Multiplier: 1.0 - Prerequisites, core concepts
    STANDARD = "standard"          # Multiplier: 0.7 - Regular curriculum topics
    PERIPHERAL = "peripheral"      # Multiplier: 0.3 - Enrichment, optional content


TOPIC_WEIGHT_MULTIPLIERS: dict[TopicWeight, float] = {
    TopicWeight.FOUNDATIONAL: 1.0,
    TopicWeight.STANDARD: 0.7,
    TopicWeight.PERIPHERAL: 0.3,
}


class GroundTruthTopic(BaseModel):
    """
    A topic with known ground truth for testing.
    
    Used to verify that the pipeline correctly extracts and preserves topics.
    """
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, description="Topic title")
    weight: TopicWeight = Field(
        default=TopicWeight.STANDARD,
        description="Importance classification"
    )
    learning_outcomes: list[str] = Field(
        default_factory=list,
        description="Expected learning outcomes"
    )
    is_present: bool = Field(
        default=True,
        description="Whether topic should be present in curriculum"
    )
    
    @property
    def weight_multiplier(self) -> float:
        """Get the numeric weight multiplier for this topic."""
        return TOPIC_WEIGHT_MULTIPLIERS[self.weight]


class GroundTruth(BaseModel):
    """
    Known ground truth for a synthetic curriculum.
    
    Contains all the expected topics, removed topics, and expected behavior
    for pipeline validation.
    """
    topics: list[GroundTruthTopic] = Field(
        default_factory=list,
        description="Topics that should be extracted"
    )
    removed_topics: list[GroundTruthTopic] = Field(
        default_factory=list,
        description="Topics intentionally removed (should NOT appear)"
    )
    expected_grade: str = Field(description="Expected grade level")
    expected_subject: str = Field(description="Expected subject")
    expected_jurisdiction: str = Field(
        default="national",
        description="Expected jurisdiction level"
    )
    
    def get_present_topics(self) -> list[GroundTruthTopic]:
        """Get topics that should be present after extraction."""
        return [t for t in self.topics if t.is_present]
    
    def get_foundational_topics(self) -> list[GroundTruthTopic]:
        """Get only foundational (core) topics."""
        return [t for t in self.topics if t.weight == TopicWeight.FOUNDATIONAL and t.is_present]
    
    def calculate_max_weighted_score(self) -> float:
        """Calculate maximum possible weighted score."""
        return sum(t.weight_multiplier for t in self.get_present_topics())


class NoiseLevel(str, Enum):
    """Noise levels for synthetic PDF generation."""
    NONE = "none"           # Clean document
    LOW = "low"             # Minor artifacts
    MEDIUM = "medium"       # Noticeable degradation
    HIGH = "high"           # Severe OCR challenges


class StructureCorruption(str, Enum):
    """Types of structure corruption to simulate."""
    NONE = "none"
    MISSING_TABLES = "missing_tables"
    MALFORMED_HEADINGS = "malformed_headings"
    MIXED_LAYOUTS = "mixed_layouts"
    SCANNED_IMAGE = "scanned_image"


class JurisdictionAmbiguity(str, Enum):
    """Types of jurisdiction ambiguity to simulate."""
    NONE = "none"
    CONFLICTING_METADATA = "conflicting_metadata"
    MISSING_AUTHORITY = "missing_authority"
    MULTIPLE_VERSIONS = "multiple_versions"


class SyntheticCurriculumConfig(BaseModel):
    """
    Configuration for generating a synthetic curriculum.
    
    Blueprint Section 22.3: Simulator Schema
    """
    synthetic_id: str = Field(
        description="Unique identifier for this synthetic curriculum"
    )
    
    # Geographic configuration
    country: str = Field(default="Testland", description="Fake country name")
    country_code: str = Field(default="TL", description="Fake ISO-2 code")
    jurisdiction: str = Field(
        default="national",
        description="Jurisdiction level: national, state, county"
    )
    jurisdiction_name: str | None = Field(
        default=None,
        description="Name of sub-national jurisdiction"
    )
    
    # Educational configuration
    grade: str = Field(default="Grade 9", description="Grade level")
    subject: str = Field(default="Science", description="Subject area")
    
    # Noise configuration
    ocr_noise: NoiseLevel = Field(
        default=NoiseLevel.NONE,
        description="OCR noise level"
    )
    structure_noise: StructureCorruption = Field(
        default=StructureCorruption.NONE,
        description="Structure corruption type"
    )
    jurisdiction_ambiguity: JurisdictionAmbiguity = Field(
        default=JurisdictionAmbiguity.NONE,
        description="Jurisdiction ambiguity type"
    )
    
    # Ground truth
    ground_truth: GroundTruth = Field(
        description="Known correct values for validation"
    )
    
    # Numeric noise scores (0.0-1.0) for fine control
    ocr_noise_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Numeric OCR noise intensity"
    )
    structure_noise_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Numeric structure corruption intensity"
    )
    
    # Deterministic seeding (Fix #6)
    rng_seed: int | None = Field(
        default=None,
        description="RNG seed for reproducible generation. None = random."
    )

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Enforce 2-character country code."""
        if len(v) != 2:
            raise ValueError("Country code must be exactly 2 characters")
        return v.upper()


class SyntheticCurriculumOutput(BaseModel):
    """
    Output from synthetic curriculum generation.
    
    Contains the generated content and metadata for testing.
    """
    config: SyntheticCurriculumConfig = Field(
        description="Configuration used to generate this curriculum"
    )
    
    # Generated content
    content_markdown: str = Field(
        description="Generated curriculum content in Markdown"
    )
    content_pdf_path: str | None = Field(
        default=None,
        description="Path to generated PDF file (if created)"
    )
    
    # Metadata
    generated_at: date = Field(
        default_factory=date.today,
        description="Date of generation"
    )
    page_count: int = Field(default=1, ge=1)
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata including provenance"
    )
    metrics: dict[str, Any] | None = Field(
        default=None,
        description="Self-evaluation metrics including confidence scores"
    )


class PipelineTestResult(BaseModel):
    """
    Result of running a synthetic curriculum through the pipeline.
    
    Contains metrics for validation against success criteria.
    """
    synthetic_id: str = Field(description="ID of the synthetic curriculum tested")
    
    # Topic accuracy metrics
    topics_expected: int = Field(description="Number of topics in ground truth")
    topics_extracted: int = Field(description="Number of topics extracted by pipeline")
    topics_correct: int = Field(description="Number of correctly extracted topics")
    topics_missed: int = Field(description="Number of missed topics")
    topics_hallucinated: int = Field(description="Number of hallucinated topics")
    
    # Weighted metrics
    weighted_score_expected: float = Field(description="Expected weighted score")
    weighted_score_actual: float = Field(description="Actual weighted score")
    
    # Core topic metrics
    core_topics_expected: int = Field(description="Number of foundational topics")
    core_topics_correct: int = Field(description="Number of correctly extracted core topics")
    
    # Jurisdiction metrics
    jurisdiction_correct: bool = Field(description="Whether jurisdiction was correctly identified")
    
    # Calculated accuracy rates
    @property
    def topic_accuracy(self) -> float:
        """Overall topic accuracy (0.0-1.0)."""
        if self.topics_expected == 0:
            return 1.0
        return self.topics_correct / self.topics_expected
    
    @property
    def weighted_topic_accuracy(self) -> float:
        """Weighted topic accuracy (0.0-1.0)."""
        if self.weighted_score_expected == 0:
            return 1.0
        return self.weighted_score_actual / self.weighted_score_expected
    
    @property
    def core_topic_accuracy(self) -> float:
        """Core (foundational) topic accuracy (0.0-1.0)."""
        if self.core_topics_expected == 0:
            return 1.0
        return self.core_topics_correct / self.core_topics_expected
    
    @property
    def hallucination_rate(self) -> float:
        """Hallucination rate (0.0-1.0)."""
        total = self.topics_extracted
        if total == 0:
            return 0.0
        return self.topics_hallucinated / total
    
    def passes_criteria(self) -> dict[str, bool]:
        """
        Check if result passes Phase 4 success criteria.
        
        Success Criteria (Blocking):
        - Weighted topic accuracy ≥ 95%
        - Core topic accuracy ≥ 99%
        - Hallucination rate ≤ 1%
        - Jurisdiction accuracy = 100% (for this test)
        """
        return {
            "weighted_topic_accuracy": self.weighted_topic_accuracy >= 0.95,
            "core_topic_accuracy": self.core_topic_accuracy >= 0.99,
            "hallucination_rate": self.hallucination_rate <= 0.01,
            "jurisdiction_accuracy": self.jurisdiction_correct,
        }
    
    def is_passing(self) -> bool:
        """Check if all criteria pass."""
        return all(self.passes_criteria().values())


class AggregateTestResults(BaseModel):
    """
    Aggregate results across multiple synthetic curriculum tests.
    """
    results: list[PipelineTestResult] = Field(default_factory=list)
    
    @property
    def total_tests(self) -> int:
        return len(self.results)
    
    @property
    def passing_tests(self) -> int:
        return sum(1 for r in self.results if r.is_passing())
    
    @property
    def average_weighted_accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.weighted_topic_accuracy for r in self.results) / len(self.results)
    
    @property
    def average_core_accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.core_topic_accuracy for r in self.results) / len(self.results)
    
    @property
    def average_hallucination_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.hallucination_rate for r in self.results) / len(self.results)
    
    @property
    def jurisdiction_accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.jurisdiction_correct) / len(self.results)
    
    def summary(self) -> dict:
        """Generate summary for reporting."""
        return {
            "total_tests": self.total_tests,
            "passing_tests": self.passing_tests,
            "pass_rate": self.passing_tests / self.total_tests if self.total_tests > 0 else 0.0,
            "average_weighted_accuracy": self.average_weighted_accuracy,
            "average_core_accuracy": self.average_core_accuracy,
            "average_hallucination_rate": self.average_hallucination_rate,
            "jurisdiction_accuracy": self.jurisdiction_accuracy,
            "all_passing": self.passing_tests == self.total_tests,
        }
