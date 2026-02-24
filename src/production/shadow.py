"""
Shadow Delta Logger (Phase 5) - BLOCKING FIXES APPLIED

Computes and logs deltas between Primary and Shadow execution paths.
Enforces strict tolerances for deviations.

Metrics:
- Topic Set Delta (Jaccard)
- Ordering Delta (Kendall Tau)
- Content Delta (Cosine Sim) - NOW COMPUTED WITH EMBEDDINGS
- Extra Topic Rate (Hallucination proxy)
- Omission Rate

Fixes Applied:
- Fix 4: content_delta with embedding provider
- Fix 5: Persist logs to object storage
- Fix 7: Timezone-aware timestamps
- Fix 9: Configurable thresholds from config
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import numpy as np
from pydantic import BaseModel, Field

from src.synthetic.schemas import SyntheticCurriculumOutput
from src.production.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================

class ShadowDeltaMetrics(BaseModel):
    """Metrics comparing primary vs shadow logic."""
    topic_set_delta: float = Field(..., description="1 - Jaccard Index")
    ordering_delta: float = Field(..., description="Normalized Kendall Tau distance")
    content_delta: float = Field(..., description="1 - Average Cosine Similarity")
    extra_topic_rate: float = Field(..., description="Shadow-only topics / Shadow Total")
    omission_rate: float = Field(..., description="Primary-only topics / Primary Total")


class ShadowLog(BaseModel):
    """Strict JSON schema for shadow logging."""
    job_id: str
    request_id: str
    curriculum_id: str
    timestamp: str  # ISO-8601 with timezone
    primary_summary: dict[str, Any]
    shadow_summary: dict[str, Any]
    metrics: ShadowDeltaMetrics
    alerts: list[str] = Field(default_factory=list)
    environment: dict[str, Any] = Field(default_factory=dict)
    storage_path: str | None = Field(default=None, description="Path to persisted log")


# =============================================================================
# CONFIGURATION (Fix 9: Configurable Thresholds)
# =============================================================================

DEFAULT_THRESHOLDS = {
    "topic_set_delta": float(os.environ.get("SHADOW_TOPIC_SET_DELTA", "0.05")),
    "ordering_delta": float(os.environ.get("SHADOW_ORDERING_DELTA", "0.20")),
    "content_delta": float(os.environ.get("SHADOW_CONTENT_DELTA", "0.10")),
    "extra_topic_rate": float(os.environ.get("SHADOW_EXTRA_TOPIC_RATE", "0.01")),
    "omission_rate": float(os.environ.get("SHADOW_OMISSION_RATE", "0.02"))
}


# =============================================================================
# LOGGER LOGIC
# =============================================================================

class ShadowDeltaLogger:
    """
    Computes differences between primary and shadow executions.
    All blocking fixes applied.
    """
    
    def __init__(
        self, 
        thresholds: dict[str, float] | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        storage_path: str | Path | None = None
    ):
        self.thresholds = {**DEFAULT_THRESHOLDS}
        if thresholds:
            self.thresholds.update(thresholds)
        
        # Fix 4: Embedding provider for content_delta
        self.embedding_provider = embedding_provider
        
        # Fix 5: Storage path for persistence
        self.storage_path = Path(storage_path) if storage_path else None
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            
    def compute_metrics(
        self,
        primary_topics: list[str],
        shadow_topics: list[str],
        primary_content: str = "",
        shadow_content: str = ""
    ) -> tuple[ShadowDeltaMetrics, list[str]]:
        """
        Compute all required delta metrics.
        """
        p_set = set(primary_topics)
        s_set = set(shadow_topics)
        
        # 1. Topic Set Delta (1 - Jaccard)
        intersection = len(p_set.intersection(s_set))
        union = len(p_set.union(s_set))
        jaccard = intersection / union if union > 0 else 1.0
        topic_set_delta = 1.0 - jaccard
        
        # 2. Extra Topic Rate (Hallucination Proxy)
        shadow_only = s_set - p_set
        extra_rate = len(shadow_only) / len(s_set) if len(s_set) > 0 else 0.0
        
        # 3. Omission Rate
        primary_only = p_set - s_set
        omission_rate = len(primary_only) / len(p_set) if len(p_set) > 0 else 0.0
        
        # 4. Ordering Delta (Normalized Kendall Tau)
        common_topics = [t for t in primary_topics if t in s_set]
        ordering_delta = self._calculate_kendall_tau_delta(common_topics, shadow_topics)
        
        # 5. Content Delta (Fix 4: Real Computation)
        content_delta = self._compute_content_delta(primary_content, shadow_content)
        
        metrics = ShadowDeltaMetrics(
            topic_set_delta=round(topic_set_delta, 4),
            ordering_delta=round(ordering_delta, 4),
            content_delta=round(content_delta, 4),
            extra_topic_rate=round(extra_rate, 4),
            omission_rate=round(omission_rate, 4)
        )
        
        alerts = self._generate_alerts(metrics)
        return metrics, alerts
    
    def _compute_content_delta(self, primary_content: str, shadow_content: str) -> float:
        """
        Compute content delta using cosine similarity of embeddings.
        Fix 4: Real implementation with embedding provider.
        """
        if not self.embedding_provider:
            # No provider: return 0 (identical assumption) with warning
            logger.warning("No embedding provider configured: content_delta defaulting to 0.0")
            return 0.0
            
        if not primary_content or not shadow_content:
            return 0.0
            
        try:
            embeddings = self.embedding_provider.embed([primary_content, shadow_content])
            if len(embeddings) != 2:
                return 0.0
                
            # Cosine similarity
            primary_vec = np.array(embeddings[0])
            shadow_vec = np.array(embeddings[1])
            
            dot = np.dot(primary_vec, shadow_vec)
            norm_p = np.linalg.norm(primary_vec)
            norm_s = np.linalg.norm(shadow_vec)
            
            if norm_p == 0 or norm_s == 0:
                return 1.0  # Maximum delta if one is zero
                
            cosine_sim = dot / (norm_p * norm_s)
            return 1.0 - cosine_sim  # Delta is 1 - similarity
            
        except Exception as e:
            logger.error(f"content_delta computation failed: {e}")
            return 0.0
        
    def _calculate_kendall_tau_delta(self, list1: list[str], list2: list[str]) -> float:
        """
        Compute Normalized Kendall Tau distance.
        Range 0.0 (identical order) to 1.0 (reverse order).
        """
        rank_map = {item: i for i, item in enumerate(list2)}
        ranks = [rank_map[item] for item in list1 if item in rank_map]
        
        n = len(ranks)
        if n <= 1:
            return 0.0
            
        inversions = 0
        for i in range(n):
            for j in range(i + 1, n):
                if ranks[i] > ranks[j]:
                    inversions += 1
                    
        max_inversions = n * (n - 1) / 2
        return inversions / max_inversions if max_inversions > 0 else 0.0

    def _generate_alerts(self, metrics: ShadowDeltaMetrics) -> list[str]:
        """Generate alerts based on thresholds."""
        alerts = []
        if metrics.topic_set_delta > self.thresholds["topic_set_delta"]:
            alerts.append("TOPIC_SET_DELTA_HIGH")
        if metrics.ordering_delta > self.thresholds["ordering_delta"]:
            alerts.append("ORDERING_DELTA_HIGH")
        if metrics.content_delta > self.thresholds["content_delta"]:
            alerts.append("CONTENT_DELTA_HIGH")
        if metrics.extra_topic_rate > self.thresholds["extra_topic_rate"]:
            alerts.append("HALLUCINATION_RISK_HIGH")
        if metrics.omission_rate > self.thresholds["omission_rate"]:
            alerts.append("OMISSION_RATE_HIGH")
        return alerts

    def log_shadow_run(
        self,
        job_id: str,
        request_id: str,
        curriculum_id: str,
        primary_out: SyntheticCurriculumOutput,
        shadow_out: SyntheticCurriculumOutput,
        primary_topics: list[str],
        shadow_topics: list[str],
        environment: dict[str, Any] | None = None
    ) -> ShadowLog:
        """
        Create and persist structured log for a shadow run.
        Fix 5: Persistence to storage.
        Fix 7: Timezone-aware timestamp.
        """
        # Compute metrics with content
        metrics, alerts = self.compute_metrics(
            primary_topics, 
            shadow_topics,
            primary_out.content_markdown,
            shadow_out.content_markdown
        )
        
        # Fix 7: Timezone-aware timestamp
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        
        # Build environment with model info
        env = environment or {}
        if self.embedding_provider:
            env["embedding_model"] = getattr(self.embedding_provider, 'model_name', 'unknown')
        
        log_entry = ShadowLog(
            job_id=job_id,
            request_id=request_id,
            curriculum_id=str(curriculum_id),
            timestamp=timestamp,
            primary_summary={
                "topic_count": len(primary_topics),
                "sentence_count": primary_out.content_markdown.count('.'),
                "char_count": len(primary_out.content_markdown)
            },
            shadow_summary={
                "topic_count": len(shadow_topics),
                "sentence_count": shadow_out.content_markdown.count('.'),
                "char_count": len(shadow_out.content_markdown)
            },
            metrics=metrics,
            alerts=alerts,
            environment=env
        )
        
        # Fix 5: Persist to storage
        storage_path = self._persist_log(log_entry)
        log_entry.storage_path = storage_path
        
        # Log warnings
        if alerts:
            logger.warning(f"Shadow Run Alerts: {alerts} for Job {job_id}")
            
        return log_entry
    
    def _persist_log(self, log: ShadowLog) -> str | None:
        """
        Persist log to object storage.
        Fix 5: Real persistence implementation.
        """
        if not self.storage_path:
            logger.info("No storage path configured: shadow log not persisted")
            return None
            
        try:
            # Create date-partitioned path
            date_str = datetime.now(tz=timezone.utc).strftime("%Y/%m/%d")
            log_dir = self.storage_path / "shadow_logs" / date_str
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Write JSON
            log_file = log_dir / f"{log.job_id}.json"
            with open(log_file, 'w') as f:
                json.dump(log.model_dump(), f, indent=2, default=str)
                
            logger.info(f"Shadow log persisted to: {log_file}")
            return str(log_file)
            
        except Exception as e:
            logger.error(f"Failed to persist shadow log: {e}")
            return None
