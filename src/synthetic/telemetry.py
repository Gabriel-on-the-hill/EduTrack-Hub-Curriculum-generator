"""
Synthetic Pipeline Telemetry (Item #12: Logging/Artifact Retention)

Provides structured logging and artifact retention for pipeline test runs.
Enables debugging failures and tracking regression over time.

Features:
- Run-level logging with TP/FP/FN counts
- Artifact retention (per-run snapshots)
- Cosine similarity averages
- Shadow-diff alert triggers
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RunMetrics(BaseModel):
    """Metrics for a single pipeline test run."""
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Matching counts
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    # Aggregate scores
    weighted_accuracy: float = 0.0
    core_accuracy: float = 0.0
    hallucination_rate: float = 0.0
    jurisdiction_accuracy: float = 0.0
    
    # Similarity averages
    avg_jaccard_score: float = 0.0
    avg_cosine_score: float = 0.0
    
    # Test metadata
    total_tests: int = 0
    passing_tests: int = 0
    seeded: bool = False
    seed_value: int | None = None
    
    # Embedding provider tracking
    embedding_provider: str = "unknown"
    
    @property
    def pass_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.passing_tests / self.total_tests
    
    def to_log_line(self) -> str:
        """Format as single-line JSON for log aggregation."""
        return self.model_dump_json()


class ShadowDiffAlert(BaseModel):
    """Alert triggered when shadow execution differs from primary."""
    alert_id: str
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Difference details
    primary_result: dict[str, Any]
    shadow_result: dict[str, Any]
    diff_summary: str
    severity: str  # "warning" | "error" | "critical"
    
    # Affected test
    synthetic_id: str
    topic_differences: list[str] = Field(default_factory=list)


class PipelineTelemetry:
    """
    Telemetry collector for synthetic pipeline runs.
    
    Maintains run history and triggers alerts on significant differences.
    """
    
    def __init__(
        self, 
        artifact_dir: str | Path | None = None,
        retention_days: int = 30,
    ):
        """
        Initialize telemetry collector.
        
        Args:
            artifact_dir: Directory for storing run artifacts
            retention_days: Number of days to retain artifacts
        """
        self.artifact_dir = Path(artifact_dir) if artifact_dir else Path(".synthetic_runs")
        self.retention_days = retention_days
        self._current_run: RunMetrics | None = None
        self._alerts: list[ShadowDiffAlert] = []
    
    def start_run(self, run_id: str, seeded: bool = False, seed_value: int | None = None) -> RunMetrics:
        """Start a new test run."""
        self._current_run = RunMetrics(
            run_id=run_id,
            seeded=seeded,
            seed_value=seed_value,
        )
        return self._current_run
    
    def record_test(
        self,
        synthetic_id: str,
        tp: int,
        fp: int,
        fn: int,
        weighted_accuracy: float,
        core_accuracy: float,
        jaccard_score: float = 0.0,
        cosine_score: float = 0.0,
        passed: bool = True,
    ):
        """Record results from a single test."""
        if not self._current_run:
            raise RuntimeError("No active run. Call start_run() first.")
        
        run = self._current_run
        run.true_positives += tp
        run.false_positives += fp
        run.false_negatives += fn
        run.total_tests += 1
        if passed:
            run.passing_tests += 1
        
        # Update running averages
        n = run.total_tests
        run.avg_jaccard_score = ((run.avg_jaccard_score * (n-1)) + jaccard_score) / n
        run.avg_cosine_score = ((run.avg_cosine_score * (n-1)) + cosine_score) / n
        run.weighted_accuracy = ((run.weighted_accuracy * (n-1)) + weighted_accuracy) / n
        run.core_accuracy = ((run.core_accuracy * (n-1)) + core_accuracy) / n
    
    def set_embedding_provider(self, provider_name: str):
        """Record which embedding provider was used."""
        if self._current_run:
            self._current_run.embedding_provider = provider_name
    
    def finalize_run(self) -> RunMetrics:
        """Finalize and persist the current run."""
        if not self._current_run:
            raise RuntimeError("No active run to finalize.")
        
        run = self._current_run
        
        # Calculate hallucination rate
        total_produced = run.true_positives + run.false_positives
        if total_produced > 0:
            run.hallucination_rate = run.false_positives / total_produced
        
        # Save artifact
        self._save_run_artifact(run)
        
        result = run
        self._current_run = None
        return result
    
    def _save_run_artifact(self, run: RunMetrics):
        """Save run metrics to artifact directory."""
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"run_{run.run_id}_{run.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.artifact_dir / filename
        
        with open(filepath, 'w') as f:
            f.write(run.model_dump_json(indent=2))
    
    def add_shadow_diff_alert(
        self,
        run_id: str,
        synthetic_id: str,
        primary: dict,
        shadow: dict,
        differences: list[str],
        severity: str = "warning",
    ):
        """Add a shadow-diff alert."""
        import uuid
        
        alert = ShadowDiffAlert(
            alert_id=str(uuid.uuid4())[:8],
            run_id=run_id,
            synthetic_id=synthetic_id,
            primary_result=primary,
            shadow_result=shadow,
            topic_differences=differences,
            diff_summary=f"{len(differences)} topic(s) differ",
            severity=severity,
        )
        self._alerts.append(alert)
        return alert
    
    def get_alerts(self) -> list[ShadowDiffAlert]:
        """Get all alerts from current session."""
        return self._alerts.copy()
    
    def load_run_history(self, limit: int = 10) -> list[RunMetrics]:
        """Load recent run history from artifacts."""
        if not self.artifact_dir.exists():
            return []
        
        files = sorted(self.artifact_dir.glob("run_*.json"), reverse=True)[:limit]
        runs = []
        
        for f in files:
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    runs.append(RunMetrics(**data))
            except Exception:
                continue
        
        return runs


# =============================================================================
# NOVEL TOKEN DETECTION (Item #9)
# =============================================================================

class NovelTokenDetector:
    """
    Detects novel tokens that weren't in the ground truth.
    
    Useful for identifying:
    - Hallucinated content
    - Unexpected topic variations
    - OCR artifacts that produced novel terms
    """
    
    def __init__(self, ground_truth_tokens: set[str] | None = None):
        """
        Initialize with ground truth vocabulary.
        
        Args:
            ground_truth_tokens: Set of expected tokens
        """
        self._ground_truth = ground_truth_tokens or set()
        self._stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        }
    
    def add_ground_truth(self, text: str):
        """Add tokens from text to ground truth vocabulary."""
        tokens = self._tokenize(text)
        self._ground_truth.update(tokens)
    
    def _tokenize(self, text: str) -> set[str]:
        """Tokenize and normalize text."""
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        return {w for w in words if len(w) > 2 and w not in self._stop_words}
    
    def detect_novel(self, extracted_text: str) -> set[str]:
        """
        Detect tokens not in ground truth.
        
        Returns:
            Set of novel tokens
        """
        extracted_tokens = self._tokenize(extracted_text)
        return extracted_tokens - self._ground_truth
    
    def novelty_ratio(self, extracted_text: str) -> float:
        """
        Calculate ratio of novel tokens.
        
        High novelty ratio may indicate hallucination.
        """
        extracted_tokens = self._tokenize(extracted_text)
        if not extracted_tokens:
            return 0.0
        
        novel = extracted_tokens - self._ground_truth
        return len(novel) / len(extracted_tokens)
    
    def get_suspicious_tokens(
        self, 
        extracted_text: str, 
        threshold: float = 0.3,
    ) -> tuple[bool, set[str]]:
        """
        Check if novelty ratio exceeds threshold.
        
        Returns:
            Tuple of (is_suspicious, novel_tokens)
        """
        novel = self.detect_novel(extracted_text)
        ratio = self.novelty_ratio(extracted_text)
        return (ratio > threshold, novel)


# =============================================================================
# SECURITY & SYNTHETIC ID NAMESPACING (Item #13)
# =============================================================================

class SyntheticIDNamespace:
    """
    Namespace management for synthetic IDs.
    
    Ensures synthetic test data never mixes with production data by:
    - Prefixing all IDs with synthetic markers
    - Validating ID patterns
    - Maintaining separation in storage
    """
    
    SYNTHETIC_PREFIX = "SIM-"
    ALLOWED_PREFIXES = ("SIM-", "TEST-", "FIXTURE-")
    
    @classmethod
    def is_synthetic(cls, id_value: str) -> bool:
        """Check if an ID is from the synthetic namespace."""
        return any(id_value.startswith(p) for p in cls.ALLOWED_PREFIXES)
    
    @classmethod
    def validate_synthetic(cls, id_value: str) -> bool:
        """
        Validate that an ID is properly namespaced.
        
        Raises ValueError if ID looks like production data.
        """
        if not cls.is_synthetic(id_value):
            raise ValueError(
                f"ID '{id_value}' is not in synthetic namespace. "
                f"Must start with one of: {cls.ALLOWED_PREFIXES}"
            )
        return True
    
    @classmethod
    def generate_synthetic_id(cls, category: str, version: str = "V1") -> str:
        """Generate a properly namespaced synthetic ID."""
        import uuid
        short_uuid = str(uuid.uuid4())[:8].upper()
        return f"{cls.SYNTHETIC_PREFIX}{category.upper()}-{short_uuid}-{version}"
    
    @classmethod
    def ensure_separation(cls, ids: list[str]) -> None:
        """
        Ensure all IDs in a list are synthetic.
        
        Use this before running test suite to prevent data leakage.
        """
        for id_val in ids:
            cls.validate_synthetic(id_val)


# =============================================================================
# PERFORMANCE BENCHMARKING (Item #11)
# =============================================================================

class PerformanceBenchmark:
    """
    Simple performance benchmarking for CI gating.
    
    Tracks execution time and memory for pipeline operations.
    """
    
    def __init__(self, name: str):
        """Initialize benchmark with a name."""
        self.name = name
        self._start_time: float | None = None
        self._end_time: float | None = None
        self._measurements: list[float] = []
    
    def start(self):
        """Start the timer."""
        import time
        self._start_time = time.perf_counter()
    
    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        import time
        self._end_time = time.perf_counter()
        elapsed = self._end_time - (self._start_time or self._end_time)
        self._measurements.append(elapsed)
        return elapsed
    
    @property
    def avg_time(self) -> float:
        """Average execution time across measurements."""
        if not self._measurements:
            return 0.0
        return sum(self._measurements) / len(self._measurements)
    
    @property
    def max_time(self) -> float:
        """Maximum execution time."""
        return max(self._measurements) if self._measurements else 0.0
    
    def check_threshold(self, max_seconds: float) -> bool:
        """Check if performance is within threshold."""
        return self.max_time <= max_seconds
    
    def to_dict(self) -> dict:
        """Export metrics as dictionary."""
        return {
            "name": self.name,
            "measurements": len(self._measurements),
            "avg_time_seconds": self.avg_time,
            "max_time_seconds": self.max_time,
        }


class BenchmarkSuite:
    """Collection of benchmarks for CI reporting."""
    
    def __init__(self):
        self._benchmarks: dict[str, PerformanceBenchmark] = {}
    
    def get_or_create(self, name: str) -> PerformanceBenchmark:
        """Get existing or create new benchmark."""
        if name not in self._benchmarks:
            self._benchmarks[name] = PerformanceBenchmark(name)
        return self._benchmarks[name]
    
    def check_all_thresholds(self, thresholds: dict[str, float]) -> dict[str, bool]:
        """Check all benchmarks against thresholds."""
        results = {}
        for name, threshold in thresholds.items():
            if name in self._benchmarks:
                results[name] = self._benchmarks[name].check_threshold(threshold)
            else:
                results[name] = True  # No data = pass
        return results
    
    def all_passing(self, thresholds: dict[str, float]) -> bool:
        """Check if all benchmarks pass."""
        return all(self.check_all_thresholds(thresholds).values())
    
    def to_report(self) -> dict:
        """Generate benchmark report."""
        return {
            name: bench.to_dict() 
            for name, bench in self._benchmarks.items()
        }
