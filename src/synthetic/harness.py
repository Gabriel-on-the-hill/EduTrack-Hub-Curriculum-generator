"""
Pipeline Test Harness (Blueprint Section 22) — Updated

Utilities for running synthetic curricula through the pipeline
and measuring accuracy against ground truth.

UPDATES (Phase 4 Blocking Fixes):
- Uses TwoStageTopicMatcher for robust matching
- Explicit MatchingCounts with TP/FP/FN
- Formalized weighted_topic_accuracy and core_topic_accuracy
- Formalized hallucination_rate = FP / (TP + FP)
"""

from dataclasses import dataclass
from datetime import date
from typing import Callable

from pydantic import BaseModel, Field

from src.synthetic.matcher import (
    MatchingCounts,
    MatchMethod,
    MatchResult,
    TwoStageTopicMatcher,
)
from src.synthetic.schemas import (
    AggregateTestResults,
    GroundTruth,
    GroundTruthTopic,
    PipelineTestResult,
    SyntheticCurriculumConfig,
    SyntheticCurriculumOutput,
    TopicWeight,
    TOPIC_WEIGHT_MULTIPLIERS,
)


# =============================================================================
# LEGACY TOPIC MATCHER (Kept for backwards compatibility)
# =============================================================================

class TopicMatcher:
    """
    DEPRECATED: Use TwoStageTopicMatcher instead.
    
    Kept for backwards compatibility with existing tests.
    """
    
    def __init__(self, similarity_threshold: float = 0.75):
        self.similarity_threshold = similarity_threshold
    
    def calculate_similarity(self, str1: str, str2: str) -> float:
        words1 = set(str1.lower().split())
        words2 = set(str2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def find_best_match(
        self, 
        extracted_title: str, 
        ground_truth: list[GroundTruthTopic]
    ) -> tuple[GroundTruthTopic | None, float]:
        best_match = None
        best_score = 0.0
        
        for topic in ground_truth:
            score = self.calculate_similarity(extracted_title, topic.title)
            if score > best_score and score >= self.similarity_threshold:
                best_score = score
                best_match = topic
        
        return best_match, best_score
    
    def match_topics(
        self,
        extracted_topics: list[str],
        ground_truth: GroundTruth,
    ) -> dict:
        present_topics = ground_truth.get_present_topics()
        removed_topics = ground_truth.removed_topics
        
        matched = []
        unmatched_extracted = []
        matched_ground_truth = set()
        
        for extracted in extracted_topics:
            match, score = self.find_best_match(extracted, present_topics)
            
            if match:
                matched.append((extracted, match, score))
                matched_ground_truth.add(match.title)
            else:
                removed_match, _ = self.find_best_match(extracted, removed_topics)
                if removed_match:
                    unmatched_extracted.append((extracted, "removed_topic"))
                else:
                    unmatched_extracted.append((extracted, "novel"))
        
        missed = [t for t in present_topics if t.title not in matched_ground_truth]
        
        return {
            "matched": matched,
            "missed": missed,
            "hallucinated": [e[0] for e in unmatched_extracted],
        }


# =============================================================================
# ENHANCED PIPELINE TEST HARNESS
# =============================================================================

@dataclass
class DetailedTestResult:
    """
    Detailed test result with explicit metrics.
    
    Extends PipelineTestResult with matching details for debugging.
    """
    base_result: PipelineTestResult
    matching_counts: MatchingCounts
    match_details: list[tuple[str, MatchResult]]
    missed_topics: list[GroundTruthTopic]
    
    @property
    def hallucination_rate(self) -> float:
        """Explicit hallucination rate: FP / (TP + FP)"""
        return self.matching_counts.hallucination_rate
    
    @property
    def weighted_topic_accuracy(self) -> float:
        """
        Weighted topic accuracy formula:
        Σ(weight(t) × found(t)) / Σ(weight(t))
        """
        return self.base_result.weighted_topic_accuracy
    
    @property
    def core_topic_accuracy(self) -> float:
        """
        Core topic accuracy formula:
        Σ(found(t) for t where weight=FOUNDATIONAL) / |{t : weight=FOUNDATIONAL}|
        """
        return self.base_result.core_topic_accuracy


class PipelineTestHarness:
    """
    Test harness for running synthetic curricula through the pipeline.
    
    Orchestrates the full test cycle:
    1. Generate synthetic curriculum
    2. Run through extraction pipeline (or mock)
    3. Compare results against ground truth using TwoStageTopicMatcher
    4. Calculate metrics with explicit formulas
    """
    
    def __init__(
        self,
        topic_matcher: TwoStageTopicMatcher | TopicMatcher | None = None,
        extraction_fn: Callable[[SyntheticCurriculumOutput], list[str]] | None = None,
        use_legacy_matcher: bool = False,
    ):
        """
        Initialize harness.
        
        Args:
            topic_matcher: Matcher for comparing topics (TwoStage preferred)
            extraction_fn: Function to extract topics from curriculum content
            use_legacy_matcher: If True, use legacy TopicMatcher (deprecated)
        """
        if topic_matcher is not None:
            self.topic_matcher = topic_matcher
            self._use_two_stage = isinstance(topic_matcher, TwoStageTopicMatcher)
        elif use_legacy_matcher:
            self.topic_matcher = TopicMatcher()
            self._use_two_stage = False
        else:
            self.topic_matcher = TwoStageTopicMatcher()
            self._use_two_stage = True
        
        self.extraction_fn = extraction_fn or self._default_extraction
    
    def _default_extraction(self, output: SyntheticCurriculumOutput) -> list[str]:
        """Default topic extraction from markdown content."""
        topics = []
        for line in output.content_markdown.split("\n"):
            line = line.strip()
            if line.startswith("### ") and not line.startswith("### Assessment"):
                topic = line.lstrip("# ").strip()
                if topic and topic[0].isdigit():
                    parts = topic.split(". ", 1)
                    if len(parts) > 1:
                        topic = parts[1]
                topics.append(topic)
        return topics
    
    def _extract_jurisdiction(self, output: SyntheticCurriculumOutput) -> str:
        """Extract jurisdiction from content."""
        for line in output.content_markdown.split("\n"):
            if "**Jurisdiction:**" in line:
                return line.split("**Jurisdiction:**")[1].strip().lower()
        return "unknown"
    
    def run_test(
        self,
        config: SyntheticCurriculumConfig,
        output: SyntheticCurriculumOutput,
    ) -> PipelineTestResult:
        """
        Run a single test against a synthetic curriculum.
        
        Args:
            config: Configuration with ground truth
            output: Generated curriculum output
            
        Returns:
            PipelineTestResult with all metrics
        """
        ground_truth = config.ground_truth
        extracted_topics = self.extraction_fn(output)
        
        if self._use_two_stage:
            return self._run_with_two_stage(config, output, extracted_topics, ground_truth)
        else:
            return self._run_with_legacy(config, output, extracted_topics, ground_truth)
    
    def _run_with_two_stage(
        self,
        config: SyntheticCurriculumConfig,
        output: SyntheticCurriculumOutput,
        extracted_topics: list[str],
        ground_truth: GroundTruth,
    ) -> PipelineTestResult:
        """Run test with TwoStageTopicMatcher."""
        matcher = self.topic_matcher
        
        # Match all topics
        match_results, counts = matcher.match_all(extracted_topics, ground_truth)
        
        # Calculate weighted scores
        weighted_expected = ground_truth.calculate_max_weighted_score()
        weighted_actual = 0.0
        core_correct = 0
        
        for extracted, result in match_results:
            if result.matched and result.matched_topic:
                weighted_actual += result.matched_topic.weight_multiplier
                if result.matched_topic.weight == TopicWeight.FOUNDATIONAL:
                    core_correct += 1
        
        # Jurisdiction check
        extracted_jurisdiction = self._extract_jurisdiction(output)
        expected_jurisdiction = ground_truth.expected_jurisdiction.lower()
        jurisdiction_correct = extracted_jurisdiction == expected_jurisdiction
        
        return PipelineTestResult(
            synthetic_id=config.synthetic_id,
            topics_expected=len(ground_truth.get_present_topics()),
            topics_extracted=len(extracted_topics),
            topics_correct=counts.true_positives,
            topics_missed=counts.false_negatives,
            topics_hallucinated=counts.false_positives,
            weighted_score_expected=weighted_expected,
            weighted_score_actual=weighted_actual,
            core_topics_expected=len(ground_truth.get_foundational_topics()),
            core_topics_correct=core_correct,
            jurisdiction_correct=jurisdiction_correct,
        )
    
    def _run_with_legacy(
        self,
        config: SyntheticCurriculumConfig,
        output: SyntheticCurriculumOutput,
        extracted_topics: list[str],
        ground_truth: GroundTruth,
    ) -> PipelineTestResult:
        """Run test with legacy TopicMatcher (backwards compatible)."""
        match_result = self.topic_matcher.match_topics(extracted_topics, ground_truth)
        
        topics_expected = len(ground_truth.get_present_topics())
        topics_extracted = len(extracted_topics)
        topics_correct = len(match_result["matched"])
        topics_missed = len(match_result["missed"])
        topics_hallucinated = len(match_result["hallucinated"])
        
        weighted_expected = ground_truth.calculate_max_weighted_score()
        weighted_actual = sum(
            m[1].weight_multiplier for m in match_result["matched"]
        )
        
        foundational = ground_truth.get_foundational_topics()
        core_expected = len(foundational)
        core_matched = [
            m for m in match_result["matched"]
            if m[1].weight == TopicWeight.FOUNDATIONAL
        ]
        core_correct = len(core_matched)
        
        extracted_jurisdiction = self._extract_jurisdiction(output)
        expected_jurisdiction = ground_truth.expected_jurisdiction.lower()
        jurisdiction_correct = extracted_jurisdiction == expected_jurisdiction
        
        return PipelineTestResult(
            synthetic_id=config.synthetic_id,
            topics_expected=topics_expected,
            topics_extracted=topics_extracted,
            topics_correct=topics_correct,
            topics_missed=topics_missed,
            topics_hallucinated=topics_hallucinated,
            weighted_score_expected=weighted_expected,
            weighted_score_actual=weighted_actual,
            core_topics_expected=core_expected,
            core_topics_correct=core_correct,
            jurisdiction_correct=jurisdiction_correct,
        )
    
    def run_test_suite(
        self,
        configs: list[SyntheticCurriculumConfig],
        outputs: list[SyntheticCurriculumOutput],
    ) -> AggregateTestResults:
        """Run tests for a full suite of synthetic curricula."""
        if len(configs) != len(outputs):
            raise ValueError("configs and outputs must have same length")
        
        results = []
        for config, output in zip(configs, outputs):
            result = self.run_test(config, output)
            results.append(result)
        
        return AggregateTestResults(results=results)


# =============================================================================
# PASS/FAIL CRITERIA
# =============================================================================

class PassFailCriteria:
    """
    Phase 4 pass/fail criteria as named constants.
    
    From evaluation feedback:
    - weighted_topic_accuracy >= 0.95
    - core_topic_accuracy >= 0.99
    - hallucination_rate <= 0.01
    - jurisdiction_accuracy >= 0.98
    """
    WEIGHTED_TOPIC_ACCURACY_MIN: float = 0.95
    CORE_TOPIC_ACCURACY_MIN: float = 0.99
    HALLUCINATION_RATE_MAX: float = 0.01
    JURISDICTION_ACCURACY_MIN: float = 0.98


def run_pipeline_validation(
    configs: list[SyntheticCurriculumConfig],
    generator,  # SyntheticCurriculumGenerator
    use_two_stage_matcher: bool = True,
    strict_embeddings: bool = True,
) -> dict:
    """
    Run full pipeline validation.
    
    This is the main entry point for Phase 4 validation.
    
    Args:
        configs: Synthetic curriculum configurations
        generator: Generator instance
        use_two_stage_matcher: If True, use TwoStageTopicMatcher (recommended)
        strict_embeddings: If True (default), require semantic embeddings.
                          Set to False for development/testing only.
        
    Returns:
        Validation results with pass/fail status
        
    Raises:
        RuntimeError: If strict_embeddings=True and sentence-transformers unavailable
    """
    # HARD CHECK: Phase 4 certification requires semantic embeddings
    from src.synthetic.embeddings import is_embeddings_available, SENTENCE_TRANSFORMERS_AVAILABLE
    
    embeddings_available = is_embeddings_available()
    
    if strict_embeddings and use_two_stage_matcher and not embeddings_available:
        raise RuntimeError(
            "Phase 4 validation requires semantic embeddings but sentence-transformers "
            "is not installed. Install with:\n\n"
            "    pip install sentence-transformers\n\n"
            "Or set strict_embeddings=False for development (NOT for certification)."
        )
    
    # Generate all outputs
    outputs = [generator.generate(config) for config in configs]
    
    # Run harness
    harness = PipelineTestHarness(use_legacy_matcher=not use_two_stage_matcher)
    aggregate = harness.run_test_suite(configs, outputs)
    
    # Get summary
    summary = aggregate.summary()
    
    # Check against criteria
    criteria_met = {
        "weighted_topic_accuracy": summary["average_weighted_accuracy"] >= PassFailCriteria.WEIGHTED_TOPIC_ACCURACY_MIN,
        "core_topic_accuracy": summary["average_core_accuracy"] >= PassFailCriteria.CORE_TOPIC_ACCURACY_MIN,
        "hallucination_rate": summary["average_hallucination_rate"] <= PassFailCriteria.HALLUCINATION_RATE_MAX,
        "jurisdiction_accuracy": summary["jurisdiction_accuracy"] >= PassFailCriteria.JURISDICTION_ACCURACY_MIN,
    }
    
    return {
        "summary": summary,
        "criteria_met": criteria_met,
        "all_criteria_passing": all(criteria_met.values()),
        "blocks_production": not all(criteria_met.values()),
        "individual_results": [r.model_dump() for r in aggregate.results],
        "pass_fail_thresholds": {
            "weighted_topic_accuracy_min": PassFailCriteria.WEIGHTED_TOPIC_ACCURACY_MIN,
            "core_topic_accuracy_min": PassFailCriteria.CORE_TOPIC_ACCURACY_MIN,
            "hallucination_rate_max": PassFailCriteria.HALLUCINATION_RATE_MAX,
            "jurisdiction_accuracy_min": PassFailCriteria.JURISDICTION_ACCURACY_MIN,
        },
        "embeddings_available": embeddings_available,
        "strict_mode": strict_embeddings,
    }
