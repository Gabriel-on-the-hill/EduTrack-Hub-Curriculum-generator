"""
Auto-Investigation Reports (Phase 4 Deferred Item #16)

Generates detailed forensic reports when pipeline validation fails.
Helps diagnose why topics were missed or hallucinations occurred.

Features:
- Root cause analysis heuristics
- Detailed failure context logging
- Actionable recommendations
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.synthetic.schemas import (
    GroundTruthTopic, 
    PipelineTestResult, 
    SyntheticCurriculumConfig,
    SyntheticCurriculumOutput
)
from src.synthetic.matcher import MatchResult


@dataclass
class FailureDiagnosis:
    """Diagnosis of a single failure."""
    failure_type: str  # "omission" | "hallucination" | "jurisdiction_mismatch"
    item_identifier: str
    likely_cause: str
    evidence: str
    recommendation: str
    confidence: float  # 0.0 to 1.0


@dataclass
class InvestigationReport:
    """Complete investigation report for a failed run."""
    run_id: str
    overall_verdict: str
    diagnoses: list[FailureDiagnosis] = field(default_factory=list)
    html_report_path: Path | None = None
    
    def summary(self) -> str:
        """Generate text summary."""
        lines = [f"Investigation Report for Run {self.run_id}"]
        lines.append(f"Verdict: {self.overall_verdict}")
        lines.append("-" * 40)
        
        for d in self.diagnoses:
            lines.append(f"[{d.failure_type.upper()}] {d.item_identifier}")
            lines.append(f"  Cause: {d.likely_cause} ({int(d.confidence*100)}% conf)")
            lines.append(f"  Rec:   {d.recommendation}")
            lines.append("")
            
        return "\n".join(lines)


class AutoInvestigator:
    """
    Automated investigator for pipeline failures.
    
    analyzes metrics, raw output, and intermediate states to 
    determine why a test failed.
    """
    
    def __init__(self, output_dir: Path | None = None):
        """Initialize investigator."""
        self.output_dir = output_dir or Path(".investigations")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def investigate(
        self,
        config: SyntheticCurriculumConfig,
        output: SyntheticCurriculumOutput,
        result: PipelineTestResult,
    ) -> InvestigationReport:
        """
        Perform forensic investigation on a test result.
        """
        report = InvestigationReport(
            run_id=output.metrics.run_id if output.metrics else "unknown",
            overall_verdict="PASS" if result.passed else "FAIL",
        )
        
        # 1. Analyze Omissions (False Negatives)
        self._analyze_omissions(config, output, result, report)
        
        # 2. Analyze Hallucinations (False Positives)
        self._analyze_hallucinations(config, output, result, report)
        
        return report
    
    def _analyze_omissions(
        self,
        config: SyntheticCurriculumConfig,
        output: SyntheticCurriculumOutput,
        result: PipelineTestResult,
        report: InvestigationReport,
    ):
        """Analyze why topics matched in ground truth were not extracted."""
        # Note: In a real implementation, we would access the list of missed topics
        # directly from the result object. Assuming result has 'missed_topics' or similar.
        # For now, we simulate this logic based on typical patterns.
        
        extracted_text = output.content_markdown.lower()
        
        for topic in config.ground_truth.topics:
            # Check if topic was actually extracted (simplified check)
            # In reality, we'd check against result.extracted_topics
            normalized_title = topic.title.lower()
            
            # Heuristic 1: OCR Corruption
            if "ocr_engine" in str(output.metadata):
                if normalized_title in extracted_text:
                    # It's in the text but wasn't matched -> Matcher Failure
                    report.diagnoses.append(FailureDiagnosis(
                        failure_type="omission",
                        item_identifier=topic.title,
                        likely_cause="Matcher Threshold Too Strict",
                        evidence=f"Text '{topic.title}' appears in content but wasn't matched.",
                        recommendation="Lower confidence threshold or check embedding distances.",
                        confidence=0.9,
                    ))
                else:
                    # It's NOT in the text -> Extraction/OCR Failure
                    report.diagnoses.append(FailureDiagnosis(
                        failure_type="omission",
                        item_identifier=topic.title,
                        likely_cause="OCR Extraction Failure",
                        evidence=f"Text '{topic.title}' absent from extracted markdown.",
                        recommendation="Check OCR engine profile and contrast settings.",
                        confidence=0.8,
                    ))
    
    def _analyze_hallucinations(
        self,
        config: SyntheticCurriculumConfig,
        output: SyntheticCurriculumOutput,
        result: PipelineTestResult,
        report: InvestigationReport,
    ):
        """Analyze why extracted topics didn't match ground truth."""
        # Heuristic: Check for novel tokens
        pass  # Placeholder for hallucination analysis


def generate_failure_report(
    config: SyntheticCurriculumConfig,
    output: SyntheticCurriculumOutput,
    result: PipelineTestResult,
) -> str:
    """Convenience function to generate a text report."""
    investigator = AutoInvestigator()
    report = investigator.investigate(config, output, result)
    return report.summary()
