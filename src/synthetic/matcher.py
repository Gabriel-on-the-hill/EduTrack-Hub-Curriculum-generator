"""
Two-Stage Topic Matcher (Phase 4 Fix #1)

Implements the matching logic specified in evaluation feedback:
- Stage 1: Jaccard (fast path) for token-identical detection
- Stage 2: Semantic (embeddings) for paraphrase detection

Matching Rules:
- A topic is FOUND if Jaccard ≥ 0.60 OR cosine ≥ threshold
- FOUNDATIONAL topics require cosine ≥ 0.85 (token-only insufficient)
- STANDARD topics: cosine ≥ 0.75
- PERIPHERAL topics: cosine ≥ 0.70
"""

from dataclasses import dataclass
from enum import Enum

from src.synthetic.embeddings import (
    BaseEmbeddingProvider,
    EmbeddingContext,
    MatcherThresholds,
    get_embedding_provider,
)
from src.synthetic.schemas import (
    GroundTruth,
    GroundTruthTopic,
    TopicWeight,
)


class MatchMethod(str, Enum):
    """Method used to match a topic."""
    JACCARD = "jaccard"
    SEMANTIC = "semantic"
    BOTH = "both"  # Both methods matched
    NONE = "none"  # No match


@dataclass
class MatchResult:
    """Result of matching a single extracted topic."""
    matched: bool
    method: MatchMethod
    jaccard_score: float
    cosine_score: float
    matched_topic: GroundTruthTopic | None = None
    
    @property
    def best_score(self) -> float:
        """Return the higher of the two scores."""
        return max(self.jaccard_score, self.cosine_score)


@dataclass
class MatchingCounts:
    """
    Explicit match counts for metrics calculation.
    
    Formalizes the hallucination rate formula:
    hallucination_rate = FP / (TP + FP)
    """
    true_positives: int   # Extracted topics matching ground truth
    false_positives: int  # Extracted topics not in ground truth (hallucinations)
    false_negatives: int  # Ground truth topics not extracted (misses)
    
    @property
    def total_produced(self) -> int:
        """Total topics produced by extraction."""
        return self.true_positives + self.false_positives
    
    @property
    def total_expected(self) -> int:
        """Total topics expected from ground truth."""
        return self.true_positives + self.false_negatives
    
    @property
    def hallucination_rate(self) -> float:
        """
        Hallucination rate formula: FP / (TP + FP)
        
        This is the proportion of produced topics that are hallucinations.
        """
        if self.total_produced == 0:
            return 0.0
        return self.false_positives / self.total_produced
    
    @property
    def recall(self) -> float:
        """Recall: TP / (TP + FN)"""
        if self.total_expected == 0:
            return 1.0
        return self.true_positives / self.total_expected
    
    @property
    def precision(self) -> float:
        """Precision: TP / (TP + FP)"""
        if self.total_produced == 0:
            return 1.0
        return self.true_positives / self.total_produced


class TwoStageTopicMatcher:
    """
    Two-stage topic matcher using Jaccard + semantic embeddings.
    
    Stage 1 (Fast): Jaccard similarity on tokens
    Stage 2 (Semantic): Cosine similarity on embeddings
    
    A topic is matched if either stage passes threshold.
    FOUNDATIONAL topics require embedding match (token-only insufficient).
    """
    
    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        context: EmbeddingContext = EmbeddingContext.SYNTHETIC_VALIDATION,
    ):
        """
        Initialize matcher.
        
        Args:
            embedding_provider: Provider for embeddings (default: get based on context)
            context: Context for embedding provider selection
        """
        self._provider = embedding_provider or get_embedding_provider(context)
        self._embedding_cache: dict[str, list[float]] = {}
    
    def _jaccard_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate Jaccard similarity on word tokens.
        
        Jaccard = |A ∩ B| / |A ∪ B|
        """
        words1 = set(str1.lower().split())
        words2 = set(str2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding with caching."""
        if text not in self._embedding_cache:
            self._embedding_cache[text] = self._provider.embed_single(text)
        return self._embedding_cache[text]
    
    def _cosine_similarity(self, str1: str, str2: str) -> float:
        """Calculate cosine similarity using embeddings."""
        emb1 = self._get_embedding(str1)
        emb2 = self._get_embedding(str2)
        return self._provider.cosine_similarity(emb1, emb2)
    
    def _get_cosine_threshold(self, topic: GroundTruthTopic) -> float:
        """Get cosine threshold based on topic weight."""
        return MatcherThresholds.get_cosine_threshold(topic.weight.value)
    
    def match_single(
        self,
        extracted: str,
        topic: GroundTruthTopic,
    ) -> MatchResult:
        """
        Match a single extracted topic against a ground truth topic.
        
        Returns MatchResult with scores and match status.
        """
        # Stage 1: Jaccard (fast path)
        jaccard_score = self._jaccard_similarity(extracted, topic.title)
        jaccard_match = jaccard_score >= MatcherThresholds.JACCARD_THRESHOLD
        
        # Stage 2: Semantic (embeddings)
        cosine_score = self._cosine_similarity(extracted, topic.title)
        cosine_threshold = self._get_cosine_threshold(topic)
        cosine_match = cosine_score >= cosine_threshold
        
        # Determine match status
        # FOUNDATIONAL topics require embedding match (token-only insufficient)
        if topic.weight == TopicWeight.FOUNDATIONAL:
            matched = cosine_match  # Must have semantic match
        else:
            matched = jaccard_match or cosine_match
        
        # Determine method used
        if jaccard_match and cosine_match:
            method = MatchMethod.BOTH
        elif cosine_match:
            method = MatchMethod.SEMANTIC
        elif jaccard_match and topic.weight != TopicWeight.FOUNDATIONAL:
            method = MatchMethod.JACCARD
        else:
            method = MatchMethod.NONE
        
        return MatchResult(
            matched=matched,
            method=method,
            jaccard_score=jaccard_score,
            cosine_score=cosine_score,
            matched_topic=topic if matched else None,
        )
    
    def find_best_match(
        self,
        extracted: str,
        ground_truth_topics: list[GroundTruthTopic],
    ) -> MatchResult:
        """
        Find the best matching ground truth topic for an extracted topic.
        
        Returns the match with highest combined score.
        """
        best_result: MatchResult | None = None
        best_score = -1.0
        
        for topic in ground_truth_topics:
            result = self.match_single(extracted, topic)
            
            if result.matched and result.best_score > best_score:
                best_score = result.best_score
                best_result = result
        
        if best_result:
            return best_result
        
        # No match found
        return MatchResult(
            matched=False,
            method=MatchMethod.NONE,
            jaccard_score=0.0,
            cosine_score=0.0,
            matched_topic=None,
        )
    
    def match_all(
        self,
        extracted_topics: list[str],
        ground_truth: GroundTruth,
    ) -> tuple[list[tuple[str, MatchResult]], MatchingCounts]:
        """
        Match all extracted topics against ground truth.
        
        Returns:
            - List of (extracted_topic, MatchResult) tuples
            - MatchingCounts with TP/FP/FN
        """
        present_topics = ground_truth.get_present_topics()
        
        # Track which ground truth topics have been matched
        matched_gt_titles: set[str] = set()
        results: list[tuple[str, MatchResult]] = []
        
        # Match each extracted topic
        true_positives = 0
        false_positives = 0
        
        for extracted in extracted_topics:
            result = self.find_best_match(extracted, present_topics)
            results.append((extracted, result))
            
            if result.matched and result.matched_topic:
                matched_gt_titles.add(result.matched_topic.title)
                true_positives += 1
            else:
                false_positives += 1
        
        # Calculate false negatives (missed topics)
        false_negatives = len(present_topics) - len(matched_gt_titles)
        
        counts = MatchingCounts(
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
        )
        
        return results, counts
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()
