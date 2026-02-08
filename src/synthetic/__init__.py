"""
EduTrack Synthetic Curriculum Module

Provides infrastructure for generating and testing synthetic curricula
to validate pipeline correctness before production deployment.

Blueprint Section 22: Synthetic Curriculum Simulators

PHASE 4 UPDATES:
- TwoStageTopicMatcher (Jaccard + semantic embeddings)
- MatchingCounts with explicit TP/FP/FN
- OCR pattern corruptions (realistic engine profiles)
- Deterministic seeding for reproducibility
- Contextual thresholds by request type
"""

from src.synthetic.schemas import (
    TopicWeight,
    TOPIC_WEIGHT_MULTIPLIERS,
    GroundTruthTopic,
    GroundTruth,
    NoiseLevel,
    StructureCorruption,
    JurisdictionAmbiguity,
    SyntheticCurriculumConfig,
    SyntheticCurriculumOutput,
    PipelineTestResult,
    AggregateTestResults,
)
from src.synthetic.generator import (
    SyntheticCurriculumGenerator,
    OCREngineProfile,
    OCRCorruptionPatterns,
    create_biology_test_curriculum,
    create_test_suite,
)
from src.synthetic.harness import (
    TopicMatcher,
    PipelineTestHarness,
    PassFailCriteria,
    run_pipeline_validation,
)
from src.synthetic.matcher import (
    TwoStageTopicMatcher,
    MatchMethod,
    MatchResult,
    MatchingCounts,
)
from src.synthetic.embeddings import (
    EmbeddingContext,
    EmbeddingProvider,
    BaseEmbeddingProvider,
    LocalSentenceTransformerProvider,
    JaccardOnlyProvider,
    GeminiEmbeddingProvider,
    EmbeddingProviderFactory,
    MatcherThresholds,
    get_embedding_provider,
    is_embeddings_available,
    SENTENCE_TRANSFORMERS_AVAILABLE,
)
from src.synthetic.governance import (
    UniversityConfidenceThresholds,
    ContextualThresholds,
    DisclaimerLevel,
    DisclaimerGenerator,
    ProvenanceMetadata,
    GovernanceDecision,
    evaluate_governance,
)
from src.synthetic.telemetry import (
    RunMetrics,
    ShadowDiffAlert,
    PipelineTelemetry,
    NovelTokenDetector,
    SyntheticIDNamespace,
    PerformanceBenchmark,
    BenchmarkSuite,
)
from src.synthetic.shadow_diff import (
    DiffSeverity,
    ShadowExecutionResult,
    ShadowExecutor,
    ShadowDiffReporter,
)
from src.synthetic.pdf_simulation import (
    PDFBackend,
    ImageBackend,
    PDFSimulatorConfig,
    PDFSimulator,
    ImageSimulator,
    SimulatedDocument,
    is_pdf_available,
    is_image_available,
    simulate_curriculum_pdf,
    simulate_scanned_document,
)
from src.synthetic.multilingual import (
    SupportedLanguage,
    MultilingualCurriculumConfig,
    MultilingualCurriculumGenerator,
)
from src.synthetic.omission_severity import (
    OmissionSeverity,
    OmissionPenalty,
    OmissionSeverityEnforcer,
    analyze_missed_topics,
)
from src.synthetic.auto_investigation import (
    InvestigationReport,
    FailureDiagnosis,
    AutoInvestigator,
    generate_failure_report,
)
from src.synthetic.extraction_tests import (
    ExtractionTestConfig,
    ExtractionContentGenerator,
    generate_extraction_test_suite,
)

__all__ = [
    # Topic weighting
    "TopicWeight",
    "TOPIC_WEIGHT_MULTIPLIERS",
    "GroundTruthTopic",
    "GroundTruth",
    # Noise configuration
    "NoiseLevel",
    "StructureCorruption",
    "JurisdictionAmbiguity",
    # Synthetic generation
    "SyntheticCurriculumConfig",
    "SyntheticCurriculumOutput",
    "SyntheticCurriculumGenerator",
    "OCREngineProfile",
    "OCRCorruptionPatterns",
    "create_biology_test_curriculum",
    "create_test_suite",
    # Test harness (legacy)
    "TopicMatcher",
    "PipelineTestHarness",
    "PassFailCriteria",
    "run_pipeline_validation",
    # Two-stage matcher (Fix #1)
    "TwoStageTopicMatcher",
    "MatchMethod",
    "MatchResult",
    "MatchingCounts",
    # Embeddings (Fix #1)
    "EmbeddingContext",
    "EmbeddingProvider",
    "BaseEmbeddingProvider",
    "LocalSentenceTransformerProvider",
    "GeminiEmbeddingProvider",
    "EmbeddingProviderFactory",
    "MatcherThresholds",
    "get_embedding_provider",
    # Governance
    "UniversityConfidenceThresholds",
    "ContextualThresholds",
    "DisclaimerLevel",
    "DisclaimerGenerator",
    "ProvenanceMetadata",
    "GovernanceDecision",
    "evaluate_governance",
    # Telemetry (Items 9, 11, 12, 13)
    "RunMetrics",
    "ShadowDiffAlert",
    "PipelineTelemetry",
    "NovelTokenDetector",
    "SyntheticIDNamespace",
    "PerformanceBenchmark",
    "BenchmarkSuite",
    # Shadow Diff (Item 10)
    "DiffSeverity",
    "ShadowExecutionResult",
    "ShadowExecutor",
    "ShadowDiffReporter",
    # Test results
    "PipelineTestResult",
    "AggregateTestResults",
]

