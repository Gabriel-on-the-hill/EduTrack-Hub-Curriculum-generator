"""
Weighted Omission Severity (Phase 4 Deferred Item #15)

Enforces severity-based penalties for topic omissions based on weight.
Foundational topic omissions are treated more severely than peripheral ones.

Features:
- Severity levels by topic weight
- Penalty calculation for validation
- Automatic flagging of critical misses
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from src.synthetic.schemas import TopicWeight, GroundTruthTopic


class OmissionSeverity(str, Enum):
    """Severity levels for topic omissions."""
    CRITICAL = "critical"      # Foundational topic missed - blocks production
    HIGH = "high"              # Standard topic missed - requires review
    MEDIUM = "medium"          # Peripheral topic missed - warning
    LOW = "low"                # Supplementary content missed - informational


@dataclass
class OmissionPenalty:
    """Penalty configuration for omissions."""
    severity: OmissionSeverity
    weight_multiplier: float  # Penalty multiplier
    blocks_production: bool   # Whether this severity blocks release
    requires_review: bool     # Whether human review is required


# Default penalty configuration by topic weight
DEFAULT_PENALTIES: dict[TopicWeight, OmissionPenalty] = {
    TopicWeight.FOUNDATIONAL: OmissionPenalty(
        severity=OmissionSeverity.CRITICAL,
        weight_multiplier=3.0,
        blocks_production=True,
        requires_review=True,
    ),
    TopicWeight.STANDARD: OmissionPenalty(
        severity=OmissionSeverity.HIGH,
        weight_multiplier=1.5,
        blocks_production=False,
        requires_review=True,
    ),
    TopicWeight.PERIPHERAL: OmissionPenalty(
        severity=OmissionSeverity.MEDIUM,
        weight_multiplier=1.0,
        blocks_production=False,
        requires_review=False,
    ),
}


@dataclass
class OmissionReport:
    """Report of a single topic omission."""
    topic: GroundTruthTopic
    severity: OmissionSeverity
    penalty: float
    blocks_production: bool
    message: str


@dataclass
class OmissionAnalysis:
    """Complete omission analysis for a test run."""
    total_omissions: int = 0
    critical_omissions: int = 0
    high_omissions: int = 0
    medium_omissions: int = 0
    low_omissions: int = 0
    total_penalty: float = 0.0
    blocks_production: bool = False
    omission_reports: list[OmissionReport] = field(default_factory=list)
    
    @property
    def severity_breakdown(self) -> dict[str, int]:
        """Get count by severity level."""
        return {
            "critical": self.critical_omissions,
            "high": self.high_omissions,
            "medium": self.medium_omissions,
            "low": self.low_omissions,
        }
    
    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Omission Analysis: {self.total_omissions} total",
            f"  Critical: {self.critical_omissions}",
            f"  High: {self.high_omissions}",
            f"  Medium: {self.medium_omissions}",
            f"  Low: {self.low_omissions}",
            f"  Total Penalty: {self.total_penalty:.2f}",
            f"  Blocks Production: {self.blocks_production}",
        ]
        return "\n".join(lines)


class OmissionSeverityEnforcer:
    """
    Enforces weighted penalties for topic omissions.
    
    Ensures that critical (foundational) topic omissions are
    treated with appropriate severity in validation.
    """
    
    def __init__(
        self,
        penalties: dict[TopicWeight, OmissionPenalty] | None = None,
        strict_mode: bool = True,
    ):
        """
        Initialize enforcement.
        
        Args:
            penalties: Custom penalty configuration
            strict_mode: If True, foundational omissions always block
        """
        self.penalties = penalties or DEFAULT_PENALTIES
        self.strict_mode = strict_mode
    
    def analyze_omissions(
        self,
        missed_topics: list[GroundTruthTopic],
    ) -> OmissionAnalysis:
        """
        Analyze a list of missed topics and calculate severities.
        
        Args:
            missed_topics: Topics that were not extracted
            
        Returns:
            Complete omission analysis
        """
        analysis = OmissionAnalysis()
        analysis.total_omissions = len(missed_topics)
        
        for topic in missed_topics:
            penalty_config = self.penalties.get(topic.weight)
            if not penalty_config:
                continue
            
            # Calculate penalty
            base_weight = {
                TopicWeight.FOUNDATIONAL: 3.0,
                TopicWeight.STANDARD: 2.0,
                TopicWeight.PERIPHERAL: 1.0,
            }.get(topic.weight, 1.0)
            
            penalty = base_weight * penalty_config.weight_multiplier
            
            # Create report
            report = OmissionReport(
                topic=topic,
                severity=penalty_config.severity,
                penalty=penalty,
                blocks_production=penalty_config.blocks_production,
                message=self._generate_message(topic, penalty_config),
            )
            analysis.omission_reports.append(report)
            
            # Update counts
            analysis.total_penalty += penalty
            
            if penalty_config.severity == OmissionSeverity.CRITICAL:
                analysis.critical_omissions += 1
                if self.strict_mode:
                    analysis.blocks_production = True
            elif penalty_config.severity == OmissionSeverity.HIGH:
                analysis.high_omissions += 1
            elif penalty_config.severity == OmissionSeverity.MEDIUM:
                analysis.medium_omissions += 1
            else:
                analysis.low_omissions += 1
        
        return analysis
    
    def _generate_message(
        self,
        topic: GroundTruthTopic,
        penalty: OmissionPenalty,
    ) -> str:
        """Generate human-readable message for omission."""
        severity = penalty.severity.value.upper()
        return (
            f"[{severity}] Missing {topic.weight.value} topic: '{topic.title}' "
            f"(penalty: {penalty.weight_multiplier}x)"
        )
    
    def get_blocking_omissions(
        self,
        missed_topics: list[GroundTruthTopic],
    ) -> list[GroundTruthTopic]:
        """Get list of omissions that block production."""
        return [
            topic for topic in missed_topics
            if self.penalties.get(topic.weight, DEFAULT_PENALTIES[TopicWeight.STANDARD]).blocks_production
        ]
    
    def check_pass_fail(
        self,
        missed_topics: list[GroundTruthTopic],
        max_penalty: float = 10.0,
    ) -> tuple[bool, OmissionAnalysis]:
        """
        Check if omissions pass validation criteria.
        
        Args:
            missed_topics: Topics that were not extracted
            max_penalty: Maximum allowed penalty score
            
        Returns:
            Tuple of (passes, analysis)
        """
        analysis = self.analyze_omissions(missed_topics)
        
        passes = (
            not analysis.blocks_production and
            analysis.total_penalty <= max_penalty
        )
        
        return passes, analysis


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def analyze_missed_topics(
    missed_topics: list[GroundTruthTopic],
    strict_mode: bool = True,
) -> OmissionAnalysis:
    """Convenience function for omission analysis."""
    enforcer = OmissionSeverityEnforcer(strict_mode=strict_mode)
    return enforcer.analyze_omissions(missed_topics)


def get_severity_for_weight(weight: TopicWeight) -> OmissionSeverity:
    """Get severity level for a topic weight."""
    penalty = DEFAULT_PENALTIES.get(weight)
    if penalty:
        return penalty.severity
    return OmissionSeverity.MEDIUM
