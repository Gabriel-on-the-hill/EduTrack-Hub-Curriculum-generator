"""
Shadow Execution Integration (Item #10)

Enables parallel execution of primary and shadow pipelines
to detect regressions before they reach production.

Features:
- Run same input through two pipelines
- Compare outputs with diff analysis
- Trigger alerts on significant differences
- Support A/B testing of pipeline changes
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, Field

from src.synthetic.schemas import (
    SyntheticCurriculumConfig,
    SyntheticCurriculumOutput,
    PipelineTestResult,
)


T = TypeVar('T')


class DiffSeverity(str, Enum):
    """Severity level for detected differences."""
    NONE = "none"         # No difference
    INFO = "info"         # Minor cosmetic differences
    WARNING = "warning"   # Metric variance, should investigate
    ERROR = "error"       # Significant divergence
    CRITICAL = "critical" # Complete failure in one path


@dataclass
class TopicDiff:
    """Difference in a single topic between runs."""
    topic: str
    primary_matched: bool
    shadow_matched: bool
    primary_score: float
    shadow_score: float
    
    @property
    def divergence(self) -> float:
        """Absolute difference in scores."""
        return abs(self.primary_score - self.shadow_score)
    
    @property
    def is_significant(self) -> bool:
        """Check if difference is significant (>0.1 or match mismatch)."""
        return self.primary_matched != self.shadow_matched or self.divergence > 0.1


class ShadowExecutionResult(BaseModel):
    """Result of shadow execution comparison."""
    config_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Primary (production) results
    primary_result: dict[str, Any]
    primary_duration_ms: float
    
    # Shadow (experimental) results
    shadow_result: dict[str, Any]
    shadow_duration_ms: float
    
    # Comparison
    severity: DiffSeverity
    topic_diffs: list[dict] = Field(default_factory=list)
    metric_diffs: dict[str, float] = Field(default_factory=dict)
    
    # Metadata
    primary_version: str = "production"
    shadow_version: str = "experimental"
    
    @property
    def has_significant_diff(self) -> bool:
        return self.severity in (DiffSeverity.ERROR, DiffSeverity.CRITICAL)


class ShadowExecutor:
    """
    Executes inputs through primary and shadow pipelines in parallel.
    
    Use cases:
    - Testing new matching algorithms
    - Validating embedding model changes
    - Comparing extraction approaches
    """
    
    def __init__(
        self,
        primary_fn: Callable[[SyntheticCurriculumConfig, SyntheticCurriculumOutput], PipelineTestResult],
        shadow_fn: Callable[[SyntheticCurriculumConfig, SyntheticCurriculumOutput], PipelineTestResult],
        primary_version: str = "production",
        shadow_version: str = "experimental",
    ):
        """
        Initialize shadow executor.
        
        Args:
            primary_fn: Production pipeline test function
            shadow_fn: Experimental pipeline test function
            primary_version: Version label for primary
            shadow_version: Version label for shadow
        """
        self.primary_fn = primary_fn
        self.shadow_fn = shadow_fn
        self.primary_version = primary_version
        self.shadow_version = shadow_version
        self._results: list[ShadowExecutionResult] = []
    
    def execute(
        self,
        config: SyntheticCurriculumConfig,
        output: SyntheticCurriculumOutput,
    ) -> ShadowExecutionResult:
        """
        Execute both pipelines and compare results.
        
        Args:
            config: Synthetic curriculum config with ground truth
            output: Generated curriculum output
            
        Returns:
            ShadowExecutionResult with comparison
        """
        import time
        
        # Run primary
        start = time.perf_counter()
        primary_result = self.primary_fn(config, output)
        primary_duration = (time.perf_counter() - start) * 1000
        
        # Run shadow
        start = time.perf_counter()
        shadow_result = self.shadow_fn(config, output)
        shadow_duration = (time.perf_counter() - start) * 1000
        
        # Compare results
        metric_diffs = self._compare_metrics(primary_result, shadow_result)
        severity = self._determine_severity(metric_diffs)
        
        result = ShadowExecutionResult(
            config_id=config.synthetic_id,
            primary_result=primary_result.model_dump(),
            primary_duration_ms=primary_duration,
            shadow_result=shadow_result.model_dump(),
            shadow_duration_ms=shadow_duration,
            severity=severity,
            metric_diffs=metric_diffs,
            primary_version=self.primary_version,
            shadow_version=self.shadow_version,
        )
        
        self._results.append(result)
        return result
    
    def _compare_metrics(
        self,
        primary: PipelineTestResult,
        shadow: PipelineTestResult,
    ) -> dict[str, float]:
        """Compare key metrics between results."""
        return {
            "topics_correct": shadow.topics_correct - primary.topics_correct,
            "topics_missed": shadow.topics_missed - primary.topics_missed,
            "topics_hallucinated": shadow.topics_hallucinated - primary.topics_hallucinated,
            "weighted_accuracy": shadow.weighted_topic_accuracy - primary.weighted_topic_accuracy,
            "core_accuracy": shadow.core_topic_accuracy - primary.core_topic_accuracy,
            "hallucination_rate": shadow.hallucination_rate - primary.hallucination_rate,
        }
    
    def _determine_severity(self, diffs: dict[str, float]) -> DiffSeverity:
        """Determine overall severity from metric differences."""
        # Critical: significant accuracy drop
        if diffs.get("weighted_accuracy", 0) < -0.10:
            return DiffSeverity.CRITICAL
        if diffs.get("core_accuracy", 0) < -0.05:
            return DiffSeverity.CRITICAL
        
        # Error: moderate divergence
        if diffs.get("weighted_accuracy", 0) < -0.05:
            return DiffSeverity.ERROR
        if abs(diffs.get("hallucination_rate", 0)) > 0.05:
            return DiffSeverity.ERROR
        
        # Warning: minor variance
        if any(abs(v) > 0.02 for v in diffs.values()):
            return DiffSeverity.WARNING
        
        # Info: tiny differences
        if any(abs(v) > 0 for v in diffs.values()):
            return DiffSeverity.INFO
        
        return DiffSeverity.NONE
    
    def get_alerts(self, min_severity: DiffSeverity = DiffSeverity.WARNING) -> list[ShadowExecutionResult]:
        """Get results with at least the specified severity."""
        severity_order = list(DiffSeverity)
        min_idx = severity_order.index(min_severity)
        
        return [
            r for r in self._results
            if severity_order.index(r.severity) >= min_idx
        ]
    
    def summary(self) -> dict:
        """Generate summary of all shadow executions."""
        if not self._results:
            return {"total_runs": 0}
        
        return {
            "total_runs": len(self._results),
            "severity_counts": {
                s.value: sum(1 for r in self._results if r.severity == s)
                for s in DiffSeverity
            },
            "avg_primary_duration_ms": sum(r.primary_duration_ms for r in self._results) / len(self._results),
            "avg_shadow_duration_ms": sum(r.shadow_duration_ms for r in self._results) / len(self._results),
            "has_critical": any(r.severity == DiffSeverity.CRITICAL for r in self._results),
            "has_error": any(r.severity == DiffSeverity.ERROR for r in self._results),
        }
    
    def clear_results(self):
        """Clear stored results."""
        self._results.clear()


class ShadowDiffReporter:
    """
    Formats shadow diff results for reporting.
    
    Generates human-readable reports and CI-friendly output.
    """
    
    @staticmethod
    def format_result(result: ShadowExecutionResult) -> str:
        """Format a single result as text."""
        lines = [
            f"Shadow Execution: {result.config_id}",
            f"  Severity: {result.severity.value.upper()}",
            f"  Primary ({result.primary_version}): {result.primary_duration_ms:.1f}ms",
            f"  Shadow ({result.shadow_version}): {result.shadow_duration_ms:.1f}ms",
        ]
        
        if result.metric_diffs:
            lines.append("  Metric Differences:")
            for metric, diff in result.metric_diffs.items():
                if diff != 0:
                    sign = "+" if diff > 0 else ""
                    lines.append(f"    {metric}: {sign}{diff:.3f}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_summary(executor: ShadowExecutor) -> str:
        """Format summary for CI output."""
        summary = executor.summary()
        
        lines = [
            "=" * 50,
            "SHADOW EXECUTION SUMMARY",
            "=" * 50,
            f"Total Runs: {summary.get('total_runs', 0)}",
        ]
        
        counts = summary.get("severity_counts", {})
        for severity in DiffSeverity:
            count = counts.get(severity.value, 0)
            if count > 0:
                lines.append(f"  {severity.value.upper()}: {count}")
        
        if summary.get("has_critical"):
            lines.append("\n⚠️ CRITICAL DIFFERENCES DETECTED - BLOCKS DEPLOYMENT")
        elif summary.get("has_error"):
            lines.append("\n⚠️ ERRORS DETECTED - REVIEW REQUIRED")
        else:
            lines.append("\n✅ No blocking differences")
        
        return "\n".join(lines)
