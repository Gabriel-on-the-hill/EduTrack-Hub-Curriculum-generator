"""
Simple canary rollout gate evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GateThreshold:
    max_p95_latency_ms: float
    max_error_rate: float


@dataclass(frozen=True)
class GateObservation:
    p95_latency_ms: float
    error_rate: float


@dataclass
class CanaryController:
    threshold_10: GateThreshold
    threshold_50: GateThreshold
    threshold_100: GateThreshold
    traffic_percent: int = 0
    rollback_enabled: bool = False

    def advance(self, percent: int, observation: GateObservation) -> bool:
        threshold = self._threshold_for(percent)
        if observation.p95_latency_ms > threshold.max_p95_latency_ms:
            self.rollback_enabled = True
            return False
        if observation.error_rate > threshold.max_error_rate:
            self.rollback_enabled = True
            return False
        self.traffic_percent = percent
        return True

    def rollback(self) -> None:
        self.traffic_percent = 0
        self.rollback_enabled = True

    def _threshold_for(self, percent: int) -> GateThreshold:
        if percent == 10:
            return self.threshold_10
        if percent == 50:
            return self.threshold_50
        if percent == 100:
            return self.threshold_100
        raise ValueError(f"Unsupported canary percentage: {percent}")
