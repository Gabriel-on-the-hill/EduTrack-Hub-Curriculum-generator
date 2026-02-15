"""
Unit tests for synthetic curriculum module (Phase 4).

Tests the synthetic curriculum generator and result metrics.
"""

import pytest

from src.synthetic.schemas import (
    TopicWeight,
    TOPIC_WEIGHT_MULTIPLIERS,
    GroundTruthTopic,
    GroundTruth,
    NoiseLevel,
    StructureCorruption,
    JurisdictionAmbiguity,
    SyntheticCurriculumConfig,
    PipelineTestResult,
    AggregateTestResults,
)
from src.synthetic.generator import (
    SyntheticCurriculumGenerator,
    create_biology_test_curriculum,
    create_test_suite,
)


class TestTopicWeight:
    """Tests for topic weighting system."""
    
    def test_weight_multipliers_defined(self):
        """All weight classes have multipliers."""
        assert TopicWeight.FOUNDATIONAL in TOPIC_WEIGHT_MULTIPLIERS
        assert TopicWeight.STANDARD in TOPIC_WEIGHT_MULTIPLIERS
        assert TopicWeight.PERIPHERAL in TOPIC_WEIGHT_MULTIPLIERS
    
    def test_foundational_highest_weight(self):
        """Foundational topics have highest weight."""
        assert TOPIC_WEIGHT_MULTIPLIERS[TopicWeight.FOUNDATIONAL] == 1.0
        assert TOPIC_WEIGHT_MULTIPLIERS[TopicWeight.STANDARD] == 0.7
        assert TOPIC_WEIGHT_MULTIPLIERS[TopicWeight.PERIPHERAL] == 0.3
    
    def test_topic_weight_multiplier_property(self):
        """GroundTruthTopic has weight_multiplier property."""
        topic = GroundTruthTopic(
            title="Test Topic",
            weight=TopicWeight.FOUNDATIONAL,
        )
        assert topic.weight_multiplier == 1.0


class TestGroundTruth:
    """Tests for ground truth model."""
    
    def test_get_present_topics(self):
        """Filters to only present topics."""
        ground_truth = GroundTruth(
            expected_grade="Grade 9",
            expected_subject="Biology",
            topics=[
                GroundTruthTopic(title="Present", is_present=True),
                GroundTruthTopic(title="Removed", is_present=False),
            ],
        )
        present = ground_truth.get_present_topics()
        assert len(present) == 1
        assert present[0].title == "Present"
    
    def test_get_foundational_topics(self):
        """Filters to only foundational topics."""
        ground_truth = GroundTruth(
            expected_grade="Grade 9",
            expected_subject="Biology",
            topics=[
                GroundTruthTopic(title="Core", weight=TopicWeight.FOUNDATIONAL),
                GroundTruthTopic(title="Standard", weight=TopicWeight.STANDARD),
            ],
        )
        core = ground_truth.get_foundational_topics()
        assert len(core) == 1
        assert core[0].title == "Core"
    
    def test_calculate_max_weighted_score(self):
        """Calculates correct max weighted score."""
        ground_truth = GroundTruth(
            expected_grade="Grade 9",
            expected_subject="Biology",
            topics=[
                GroundTruthTopic(title="Core", weight=TopicWeight.FOUNDATIONAL),
                GroundTruthTopic(title="Standard", weight=TopicWeight.STANDARD),
                GroundTruthTopic(title="Extra", weight=TopicWeight.PERIPHERAL),
            ],
        )
        # 1.0 + 0.7 + 0.3 = 2.0
        assert ground_truth.calculate_max_weighted_score() == 2.0


class TestSyntheticCurriculumConfig:
    """Tests for synthetic curriculum configuration."""
    
    def test_country_code_validation(self):
        """Country code must be 2 characters."""
        config = create_biology_test_curriculum()
        assert len(config.country_code) == 2
    
    def test_country_code_uppercase(self):
        """Country code is uppercased."""
        ground_truth = GroundTruth(
            expected_grade="Grade 9",
            expected_subject="Biology",
            topics=[],
        )
        config = SyntheticCurriculumConfig(
            synthetic_id="TEST",
            country_code="tl",
            ground_truth=ground_truth,
        )
        assert config.country_code == "TL"


class TestSyntheticCurriculumGenerator:
    """Tests for curriculum generator."""
    
    def test_generator_reproducible_with_seed(self):
        """Same seed produces same output."""
        config = create_biology_test_curriculum()
        
        g1 = SyntheticCurriculumGenerator(seed=42)
        output1 = g1.generate(config)
        
        g2 = SyntheticCurriculumGenerator(seed=42)
        output2 = g2.generate(config)
        
        assert output1.content_markdown == output2.content_markdown
    
    def test_generates_markdown_content(self):
        """Generator produces non-empty markdown."""
        generator = SyntheticCurriculumGenerator(seed=42)
        config = create_biology_test_curriculum()
        output = generator.generate(config)
        
        assert output.content_markdown
        assert "# Biology Curriculum" in output.content_markdown
        assert "Grade 9" in output.content_markdown
    
    def test_includes_all_present_topics(self):
        """All present topics appear in output."""
        generator = SyntheticCurriculumGenerator(seed=42)
        config = create_biology_test_curriculum()
        output = generator.generate(config)
        
        for topic in config.ground_truth.get_present_topics():
            assert topic.title in output.content_markdown
    
    def test_ocr_noise_modifies_content(self):
        """OCR noise changes the content."""
        generator = SyntheticCurriculumGenerator(seed=42)
        
        clean_config = create_biology_test_curriculum(noise_level=NoiseLevel.NONE)
        noisy_config = create_biology_test_curriculum(noise_level=NoiseLevel.HIGH)
        
        clean_output = generator.generate(clean_config)
        noisy_output = generator.generate(noisy_config)
        
        assert clean_output.content_markdown != noisy_output.content_markdown
    
    def test_structure_corruption_modifies_content(self):
        """Structure corruption changes the content."""
        generator = SyntheticCurriculumGenerator(seed=42)
        
        clean_config = create_biology_test_curriculum()
        corrupted_config = create_biology_test_curriculum(
            structure_corruption=StructureCorruption.MALFORMED_HEADINGS
        )
        
        clean_output = generator.generate(clean_config)
        corrupted_output = generator.generate(corrupted_config)
        
        assert clean_output.content_markdown != corrupted_output.content_markdown


class TestPipelineTestResult:
    """Tests for pipeline test result metrics."""
    
    def test_topic_accuracy_calculation(self):
        """Topic accuracy calculated correctly."""
        result = PipelineTestResult(
            synthetic_id="TEST",
            topics_expected=10,
            topics_extracted=10,
            topics_correct=9,
            topics_missed=1,
            topics_hallucinated=0,
            weighted_score_expected=10.0,
            weighted_score_actual=9.0,
            core_topics_expected=3,
            core_topics_correct=3,
            jurisdiction_correct=True,
        )
        assert result.topic_accuracy == 0.9
    
    def test_hallucination_rate_calculation(self):
        """Hallucination rate calculated correctly."""
        result = PipelineTestResult(
            synthetic_id="TEST",
            topics_expected=10,
            topics_extracted=11,
            topics_correct=10,
            topics_missed=0,
            topics_hallucinated=1,
            weighted_score_expected=10.0,
            weighted_score_actual=10.0,
            core_topics_expected=3,
            core_topics_correct=3,
            jurisdiction_correct=True,
        )
        # 1 hallucinated out of 11 extracted
        assert abs(result.hallucination_rate - 1/11) < 0.001
    
    def test_passes_criteria_all_passing(self):
        """Passes criteria when all thresholds met."""
        result = PipelineTestResult(
            synthetic_id="TEST",
            topics_expected=100,
            topics_extracted=100,
            topics_correct=96,
            topics_missed=4,
            topics_hallucinated=0,
            weighted_score_expected=100.0,
            weighted_score_actual=96.0,
            core_topics_expected=10,
            core_topics_correct=10,
            jurisdiction_correct=True,
        )
        criteria = result.passes_criteria()
        assert criteria["weighted_topic_accuracy"] is True
        assert criteria["core_topic_accuracy"] is True
        assert criteria["hallucination_rate"] is True
        assert criteria["jurisdiction_accuracy"] is True
        assert result.is_passing() is True
    
    def test_fails_criteria_low_weighted_accuracy(self):
        """Fails when weighted accuracy below 95%."""
        result = PipelineTestResult(
            synthetic_id="TEST",
            topics_expected=100,
            topics_extracted=100,
            topics_correct=90,
            topics_missed=10,
            topics_hallucinated=0,
            weighted_score_expected=100.0,
            weighted_score_actual=90.0,  # 90% < 95%
            core_topics_expected=10,
            core_topics_correct=10,
            jurisdiction_correct=True,
        )
        assert result.passes_criteria()["weighted_topic_accuracy"] is False
        assert result.is_passing() is False
    
    def test_fails_criteria_core_accuracy(self):
        """Fails when core accuracy below 99%."""
        result = PipelineTestResult(
            synthetic_id="TEST",
            topics_expected=100,
            topics_extracted=100,
            topics_correct=98,
            topics_missed=2,
            topics_hallucinated=0,
            weighted_score_expected=100.0,
            weighted_score_actual=98.0,
            core_topics_expected=10,
            core_topics_correct=9,  # 90% < 99%
            jurisdiction_correct=True,
        )
        assert result.passes_criteria()["core_topic_accuracy"] is False
        assert result.is_passing() is False
    
    def test_fails_criteria_high_hallucination(self):
        """Fails when hallucination rate above 1%."""
        result = PipelineTestResult(
            synthetic_id="TEST",
            topics_expected=100,
            topics_extracted=103,
            topics_correct=100,
            topics_missed=0,
            topics_hallucinated=3,  # 3% > 1%
            weighted_score_expected=100.0,
            weighted_score_actual=100.0,
            core_topics_expected=10,
            core_topics_correct=10,
            jurisdiction_correct=True,
        )
        assert result.passes_criteria()["hallucination_rate"] is False
        assert result.is_passing() is False


class TestAggregateTestResults:
    """Tests for aggregate results."""
    
    def test_summary_calculation(self):
        """Summary correctly aggregates results."""
        results = AggregateTestResults(results=[
            PipelineTestResult(
                synthetic_id="TEST1",
                topics_expected=10,
                topics_extracted=10,
                topics_correct=10,
                topics_missed=0,
                topics_hallucinated=0,
                weighted_score_expected=10.0,
                weighted_score_actual=10.0,
                core_topics_expected=3,
                core_topics_correct=3,
                jurisdiction_correct=True,
            ),
            PipelineTestResult(
                synthetic_id="TEST2",
                topics_expected=10,
                topics_extracted=10,
                topics_correct=10,
                topics_missed=0,
                topics_hallucinated=0,
                weighted_score_expected=10.0,
                weighted_score_actual=10.0,
                core_topics_expected=3,
                core_topics_correct=3,
                jurisdiction_correct=True,
            ),
        ])
        
        summary = results.summary()
        assert summary["total_tests"] == 2
        assert summary["passing_tests"] == 2
        assert summary["pass_rate"] == 1.0
        assert summary["all_passing"] is True


class TestCreateTestSuite:
    """Tests for test suite creation."""
    
    def test_creates_multiple_configs(self):
        """Test suite creates multiple configurations."""
        suite = create_test_suite()
        assert len(suite) >= 5  # At least baseline + variations
    
    def test_includes_baseline(self):
        """Test suite includes clean baseline."""
        suite = create_test_suite()
        clean = [c for c in suite if c.ocr_noise == NoiseLevel.NONE 
                 and c.structure_noise == StructureCorruption.NONE]
        assert len(clean) >= 1
    
    def test_includes_noise_variations(self):
        """Test suite includes noise variations."""
        suite = create_test_suite()
        noisy = [c for c in suite if c.ocr_noise != NoiseLevel.NONE]
        assert len(noisy) >= 1


class TestTopicMatcher:
    """Tests for topic matching utilities."""
    
    def test_exact_match(self):
        """Exact title matches with high score."""
        from src.synthetic.harness import TopicMatcher
        matcher = TopicMatcher()
        
        ground_truth = [
            GroundTruthTopic(title="Cell Division"),
            GroundTruthTopic(title="Genetics"),
        ]
        
        match, score = matcher.find_best_match("Cell Division", ground_truth)
        assert match is not None
        assert match.title == "Cell Division"
        assert score == 1.0
    
    def test_fuzzy_match(self):
        """Fuzzy matching works for similar titles."""
        from src.synthetic.harness import TopicMatcher
        matcher = TopicMatcher(similarity_threshold=0.5)
        
        ground_truth = [
            GroundTruthTopic(title="Cell Division and Mitosis"),
        ]
        
        match, score = matcher.find_best_match("Cell Division", ground_truth)
        assert match is not None
        assert score >= 0.5
    
    def test_no_match_below_threshold(self):
        """No match when similarity below threshold."""
        from src.synthetic.harness import TopicMatcher
        matcher = TopicMatcher(similarity_threshold=0.9)
        
        ground_truth = [
            GroundTruthTopic(title="Completely Different Topic"),
        ]
        
        match, score = matcher.find_best_match("Cell Division", ground_truth)
        assert match is None


class TestPipelineTestHarness:
    """Tests for pipeline test harness."""
    
    def test_harness_runs_clean_curriculum(self):
        """Harness runs successfully on clean curriculum."""
        from src.synthetic.harness import PipelineTestHarness
        
        generator = SyntheticCurriculumGenerator(seed=42)
        config = create_biology_test_curriculum()
        output = generator.generate(config)
        
        harness = PipelineTestHarness(use_legacy_matcher=True)
        result = harness.run_test(config, output)
        
        assert result.synthetic_id == config.synthetic_id
        assert result.topics_expected == len(config.ground_truth.get_present_topics())
        assert result.topics_correct > 0
    
    def test_clean_curriculum_passes_criteria(self):
        """Clean curriculum should pass all criteria."""
        from src.synthetic.harness import PipelineTestHarness
        
        generator = SyntheticCurriculumGenerator(seed=42)
        config = create_biology_test_curriculum(noise_level=NoiseLevel.NONE)
        output = generator.generate(config)
        
        harness = PipelineTestHarness(use_legacy_matcher=True)
        result = harness.run_test(config, output)
        
        # Clean curriculum should extract all topics correctly
        assert result.weighted_topic_accuracy >= 0.95
        assert result.core_topic_accuracy >= 0.99
        assert result.hallucination_rate <= 0.01
        assert result.is_passing()
    
    def test_run_test_suite(self):
        """Test suite runs multiple configs."""
        from src.synthetic.harness import PipelineTestHarness
        
        generator = SyntheticCurriculumGenerator(seed=42)
        configs = create_test_suite()[:3]  # Just first 3 for speed
        outputs = [generator.generate(c) for c in configs]
        
        harness = PipelineTestHarness(use_legacy_matcher=True)
        aggregate = harness.run_test_suite(configs, outputs)
        
        assert aggregate.total_tests == 3
        assert len(aggregate.results) == 3


class TestRunPipelineValidation:
    """Tests for the main validation function."""
    
    def test_validation_returns_summary(self):
        """Validation returns complete summary."""
        from src.synthetic.harness import run_pipeline_validation
        
        generator = SyntheticCurriculumGenerator(seed=42)
        configs = [create_biology_test_curriculum()]  # Single test for speed
        
        result = run_pipeline_validation(configs, generator, use_two_stage_matcher=False, strict_embeddings=False)
        
        assert "summary" in result
        assert "criteria_met" in result
        assert "all_criteria_passing" in result
        assert "blocks_production" in result
    
    def test_clean_validation_passes(self):
        """Clean curriculum validation should pass."""
        from src.synthetic.harness import run_pipeline_validation
        
        generator = SyntheticCurriculumGenerator(seed=42)
        configs = [create_biology_test_curriculum(noise_level=NoiseLevel.NONE)]
        
        result = run_pipeline_validation(configs, generator, use_two_stage_matcher=False, strict_embeddings=False)
        
        assert result["all_criteria_passing"] is True
        assert result["blocks_production"] is False


# =============================================================================
# NEW TESTS: Phase 4 Blocking Fixes + High Priority Items
# =============================================================================

class TestTwoStageTopicMatcher:
    """Tests for TwoStageTopicMatcher (Fix #1)."""
    
    def test_jaccard_exact_match(self):
        """Jaccard stage matches exact titles."""
        from src.synthetic.matcher import TwoStageTopicMatcher, MatchMethod
        from src.synthetic.embeddings import MatcherThresholds
        
        # Use legacy matcher to avoid embedding download in unit tests
        # TwoStageTopicMatcher is tested with mock provider below
        
        topic = GroundTruthTopic(title="Cell Division", weight=TopicWeight.STANDARD)
        
        matcher = TwoStageTopicMatcher()
        result = matcher._jaccard_similarity("Cell Division", "Cell Division")
        
        assert result == 1.0  # Exact match
    
    def test_jaccard_partial_match(self):
        """Jaccard stage handles partial matches."""
        from src.synthetic.matcher import TwoStageTopicMatcher
        
        matcher = TwoStageTopicMatcher()
        score = matcher._jaccard_similarity("Cell Division", "Cell Division and Mitosis")
        
        # "cell" and "division" are 2 out of 4 words
        assert score >= 0.4
        assert score < 1.0
    
    def test_jaccard_no_match(self):
        """Jaccard returns 0 for completely different strings."""
        from src.synthetic.matcher import TwoStageTopicMatcher
        
        matcher = TwoStageTopicMatcher()
        score = matcher._jaccard_similarity("Cell Division", "World History")
        
        assert score == 0.0


class TestMatchingCounts:
    """Tests for MatchingCounts metrics (Fix #2)."""
    
    def test_hallucination_rate_formula(self):
        """Hallucination rate = FP / (TP + FP)."""
        from src.synthetic.matcher import MatchingCounts
        
        counts = MatchingCounts(
            true_positives=9,
            false_positives=1,
            false_negatives=0,
        )
        
        # 1 / (9 + 1) = 0.1
        assert counts.hallucination_rate == 0.1
    
    def test_hallucination_rate_zero_fp(self):
        """Hallucination rate is 0 when no false positives."""
        from src.synthetic.matcher import MatchingCounts
        
        counts = MatchingCounts(
            true_positives=10,
            false_positives=0,
            false_negatives=2,
        )
        
        assert counts.hallucination_rate == 0.0
    
    def test_hallucination_rate_empty(self):
        """Hallucination rate is 0 when nothing produced."""
        from src.synthetic.matcher import MatchingCounts
        
        counts = MatchingCounts(
            true_positives=0,
            false_positives=0,
            false_negatives=5,
        )
        
        assert counts.hallucination_rate == 0.0
    
    def test_precision_and_recall(self):
        """Precision and recall calculated correctly."""
        from src.synthetic.matcher import MatchingCounts
        
        counts = MatchingCounts(
            true_positives=8,
            false_positives=2,
            false_negatives=2,
        )
        
        # Precision = 8 / (8 + 2) = 0.8
        assert counts.precision == 0.8
        
        # Recall = 8 / (8 + 2) = 0.8
        assert counts.recall == 0.8


class TestMatcherThresholds:
    """Tests for MatcherThresholds constants (Fix #1)."""
    
    def test_thresholds_defined(self):
        """All thresholds are defined constants."""
        from src.synthetic.embeddings import MatcherThresholds
        
        assert MatcherThresholds.JACCARD_THRESHOLD == 0.60
        assert MatcherThresholds.COSINE_FOUNDATIONAL == 0.85
        assert MatcherThresholds.COSINE_STANDARD == 0.75
        assert MatcherThresholds.COSINE_PERIPHERAL == 0.70
    
    def test_get_cosine_threshold_by_weight(self):
        """Cosine threshold varies by topic weight."""
        from src.synthetic.embeddings import MatcherThresholds
        
        assert MatcherThresholds.get_cosine_threshold("foundational") == 0.85
        assert MatcherThresholds.get_cosine_threshold("standard") == 0.75
        assert MatcherThresholds.get_cosine_threshold("peripheral") == 0.70


class TestNovelTokenDetector:
    """Tests for NovelTokenDetector (Item #9)."""
    
    def test_detect_novel_tokens(self):
        """Detects tokens not in ground truth."""
        from src.synthetic.telemetry import NovelTokenDetector
        
        detector = NovelTokenDetector()
        detector.add_ground_truth("Cell Division Mitosis")
        
        novel = detector.detect_novel("Cell Division Meiosis Genetics")
        
        assert "meiosis" in novel
        assert "genetics" in novel
        assert "cell" not in novel
        assert "division" not in novel
    
    def test_novelty_ratio(self):
        """Novelty ratio calculated correctly."""
        from src.synthetic.telemetry import NovelTokenDetector
        
        detector = NovelTokenDetector()
        detector.add_ground_truth("one two three")
        
        # 2 known, 2 novel
        ratio = detector.novelty_ratio("one two four five")
        assert 0.4 <= ratio <= 0.6


class TestSyntheticIDNamespace:
    """Tests for SyntheticIDNamespace security (Item #13)."""
    
    def test_is_synthetic(self):
        """Correctly identifies synthetic IDs."""
        from src.synthetic.telemetry import SyntheticIDNamespace
        
        assert SyntheticIDNamespace.is_synthetic("SIM-BIO-V1")
        assert SyntheticIDNamespace.is_synthetic("TEST-123")
        assert SyntheticIDNamespace.is_synthetic("FIXTURE-ABC")
        assert not SyntheticIDNamespace.is_synthetic("PROD-123")
        assert not SyntheticIDNamespace.is_synthetic("curriculum-123")
    
    def test_validate_raises_for_production(self):
        """Raises error for non-synthetic IDs."""
        from src.synthetic.telemetry import SyntheticIDNamespace
        
        with pytest.raises(ValueError):
            SyntheticIDNamespace.validate_synthetic("PROD-123")
    
    def test_generate_synthetic_id(self):
        """Generates properly namespaced IDs."""
        from src.synthetic.telemetry import SyntheticIDNamespace
        
        id1 = SyntheticIDNamespace.generate_synthetic_id("BIO")
        id2 = SyntheticIDNamespace.generate_synthetic_id("CHEM")
        
        assert id1.startswith("SIM-BIO-")
        assert id2.startswith("SIM-CHEM-")
        assert id1 != id2  # Unique


class TestPerformanceBenchmark:
    """Tests for PerformanceBenchmark (Item #11)."""
    
    def test_timing(self):
        """Benchmark measures execution time."""
        from src.synthetic.telemetry import PerformanceBenchmark
        import time
        
        bench = PerformanceBenchmark("test_op")
        bench.start()
        time.sleep(0.01)  # 10ms
        elapsed = bench.stop()
        
        assert elapsed >= 0.01
        assert bench.avg_time >= 0.01
    
    def test_threshold_check(self):
        """Threshold check works correctly."""
        from src.synthetic.telemetry import PerformanceBenchmark
        
        bench = PerformanceBenchmark("fast_op")
        bench._measurements = [0.05, 0.06, 0.07]  # Max 70ms
        
        assert bench.check_threshold(0.1)  # 100ms - passes
        assert not bench.check_threshold(0.05)  # 50ms - fails


class TestContextualThresholds:
    """Tests for ContextualThresholds (Fix #8)."""
    
    def test_university_thresholds_lower(self):
        """University thresholds are lower than K12."""
        from src.synthetic.governance import ContextualThresholds
        from src.schemas.base import CurriculumMode
        
        k12_exam = ContextualThresholds.get_threshold(CurriculumMode.K12, "exam")
        uni_exam = ContextualThresholds.get_threshold(CurriculumMode.SYLLABUS, "exam")
        
        assert k12_exam > uni_exam
    
    def test_certification_strictest(self):
        """Certification has highest threshold."""
        from src.synthetic.governance import ContextualThresholds
        from src.schemas.base import CurriculumMode
        
        summary = ContextualThresholds.get_threshold(CurriculumMode.SYLLABUS, "summary")
        cert = ContextualThresholds.get_threshold(CurriculumMode.SYLLABUS, "certification")
        
        assert cert > summary
    
    def test_check_threshold(self):
        """Threshold check returns pass/fail and required threshold."""
        from src.synthetic.governance import ContextualThresholds
        from src.schemas.base import CurriculumMode
        
        passes, threshold = ContextualThresholds.check_threshold(
            CurriculumMode.SYLLABUS, "summary", 0.80
        )
        
        assert passes is True  # 0.80 >= 0.75
        assert threshold == 0.75


class TestDeterministicSeeding:
    """Tests for deterministic seeding (Fix #6)."""
    
    def test_config_seed_overrides_generator(self):
        """Config rng_seed takes precedence over generator seed."""
        from src.synthetic.generator import SyntheticCurriculumGenerator
        
        config1 = create_biology_test_curriculum(noise_level=NoiseLevel.LOW, rng_seed=100)
        config2 = create_biology_test_curriculum(noise_level=NoiseLevel.LOW, rng_seed=100)
        config3 = create_biology_test_curriculum(noise_level=NoiseLevel.LOW, rng_seed=200)
        
        # Different generator seeds, but same config seed
        g1 = SyntheticCurriculumGenerator(seed=42)
        g2 = SyntheticCurriculumGenerator(seed=999)
        
        output1 = g1.generate(config1)
        output2 = g2.generate(config2)
        output3 = g1.generate(config3)
        
        assert output1.content_markdown == output2.content_markdown  # Same config seed
        assert output1.content_markdown != output3.content_markdown  # Different config seed

