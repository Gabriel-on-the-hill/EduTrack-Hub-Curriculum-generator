"""
Synthetic Curriculum Generator (Blueprint Section 22) — Updated

Generates synthetic curricula with controlled variations for pipeline testing.
Produces markdown content that can optionally be converted to PDF.

UPDATES (Phase 4 Blocking Fixes):
- OCR pattern corruptions (realistic engine-specific errors)
- Deterministic seeding from config.rng_seed
- OCR engine profiles (Tesseract-like, Vision API)
"""

import random
import string
from datetime import date
from enum import Enum
from uuid import uuid4

from src.synthetic.schemas import (
    GroundTruth,
    GroundTruthTopic,
    JurisdictionAmbiguity,
    NoiseLevel,
    StructureCorruption,
    SyntheticCurriculumConfig,
    SyntheticCurriculumOutput,
    TopicWeight,
)


# =============================================================================
# OCR CORRUPTION PATTERNS (Fix #5)
# =============================================================================

class OCREngineProfile(str, Enum):
    """OCR engine simulation profiles."""
    TESSERACT = "tesseract"  # Common open-source OCR
    VISION_API = "vision_api"  # Cloud Vision-like API
    POOR_SCAN = "poor_scan"  # Low-quality scanned document


class OCRCorruptionPatterns:
    """
    Realistic OCR engine error patterns.
    
    Based on actual OCR failure modes:
    - Character confusions (visually similar glyphs)
    - Merged/split tokens
    - Punctuation errors
    - Accent stripping
    """
    
    # Common character confusions by engine type
    TESSERACT_CONFUSIONS: dict[str, list[str]] = {
        'O': ['0', 'Q', 'o'],
        '0': ['O', 'o', 'D'],
        'l': ['1', 'I', '|', 'i'],
        '1': ['l', 'I', '|', 'i'],
        'I': ['l', '1', '|', 'i'],
        'i': ['l', '1', 'I'],
        'S': ['5', '$'],
        '5': ['S', '$'],
        'B': ['8', '6'],
        '8': ['B', '6'],
        'G': ['6', 'C'],
        'g': ['9', 'q'],
        'q': ['9', 'g'],
        'Z': ['2', '7'],
        'z': ['2'],
        'n': ['r', 'h'],
        'h': ['n', 'b'],
        'c': ['e', 'o'],
        'e': ['c', 'o'],
    }
    
    VISION_API_CONFUSIONS: dict[str, list[str]] = {
        # Vision API is generally better, fewer confusions
        'l': ['1', 'I'],
        '0': ['O'],
        'O': ['0'],
    }
    
    # Token-level corruptions
    MERGED_TOKENS: dict[str, str] = {
        'rn': 'm',  # Very common
        'cl': 'd',
        'ri': 'n',
        'vv': 'w',
    }
    
    SPLIT_TOKENS: dict[str, str] = {
        'm': 'rn',
        'w': 'vv',
    }
    
    # Punctuation that gets dropped
    PUNCTUATION_DROPS = ['.', ',', ':', ';', "'", '"', '-']
    
    # Accent stripping (common in poor OCR)
    ACCENT_STRIP: dict[str, str] = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ñ': 'n', 'ç': 'c',
    }


class SyntheticCurriculumGenerator:
    """
    Generator for synthetic curriculum test fixtures.
    
    Creates curriculum documents with controlled noise levels,
    structure corruption, and jurisdiction ambiguity for testing.
    """
    
    def __init__(self, seed: int | None = None):
        """
        Initialize generator with optional random seed for reproducibility.
        
        Args:
            seed: Global seed for the generator. Can be overridden per-config.
        """
        self._global_seed = seed
        self.random = random.Random(seed)
    
    def generate(self, config: SyntheticCurriculumConfig) -> SyntheticCurriculumOutput:
        """
        Generate a synthetic curriculum based on configuration.
        
        Uses config.rng_seed if provided, otherwise falls back to global seed.
        """
        # Deterministic seeding (Fix #6): use config seed if provided
        effective_seed = config.rng_seed if config.rng_seed is not None else self._global_seed
        if effective_seed is not None:
            self.random = random.Random(effective_seed)
        
        # Build base curriculum content
        content = self._build_curriculum_content(config)
        
        # Apply structure corruption
        content = self._apply_structure_corruption(content, config)
        
        # Apply OCR noise (pattern-based)
        content = self._apply_ocr_pattern_noise(content, config)
        
        # Apply jurisdiction ambiguity
        content = self._apply_jurisdiction_ambiguity(content, config)
        
        return SyntheticCurriculumOutput(
            config=config,
            content_markdown=content,
            generated_at=date.today(),
            page_count=max(1, len(content) // 3000),
        )
    
    def _build_curriculum_content(self, config: SyntheticCurriculumConfig) -> str:
        """Build the base curriculum content from ground truth."""
        ground_truth = config.ground_truth
        
        lines = [
            f"# {config.subject} Curriculum",
            f"## {config.grade}",
            "",
            f"**Country:** {config.country}",
            f"**Jurisdiction:** {config.jurisdiction.title()}",
        ]
        
        if config.jurisdiction_name:
            lines.append(f"**Region:** {config.jurisdiction_name}")
        
        lines.extend([
            "",
            "---",
            "",
            "## Learning Objectives",
            "",
        ])
        
        # Add topics from ground truth
        for i, topic in enumerate(ground_truth.topics, 1):
            if topic.is_present:
                lines.extend(self._format_topic(i, topic))
        
        lines.extend([
            "",
            "---",
            "",
            "## Assessment Guidelines",
            "",
            "Students will be assessed on their understanding of the above topics",
            "through a combination of written examinations, practical demonstrations,",
            "and project-based assessments.",
            "",
        ])
        
        return "\n".join(lines)
    
    def _format_topic(self, number: int, topic: GroundTruthTopic) -> list[str]:
        """Format a single topic for the curriculum."""
        lines = [
            f"### {number}. {topic.title}",
            "",
        ]
        
        if topic.learning_outcomes:
            lines.append("**Learning Outcomes:**")
            lines.append("")
            for outcome in topic.learning_outcomes:
                lines.append(f"- {outcome}")
            lines.append("")
        
        lines.append(f"<!-- weight: {topic.weight.value} -->")
        lines.append("")
        
        return lines
    
    def _apply_ocr_pattern_noise(
        self, 
        content: str, 
        config: SyntheticCurriculumConfig,
        profile: OCREngineProfile = OCREngineProfile.TESSERACT,
    ) -> str:
        """
        Apply realistic OCR pattern noise (Fix #5).
        
        Uses confusion matrices and token-level corruptions that
        match real OCR engine behavior.
        """
        if config.ocr_noise == NoiseLevel.NONE and config.ocr_noise_score == 0:
            return content
        
        # Determine noise intensity
        if config.ocr_noise_score > 0:
            intensity = config.ocr_noise_score
        else:
            intensity = {
                NoiseLevel.NONE: 0.0,
                NoiseLevel.LOW: 0.02,
                NoiseLevel.MEDIUM: 0.08,
                NoiseLevel.HIGH: 0.20,
            }[config.ocr_noise]
        
        if intensity == 0:
            return content
        
        # Get confusion matrix for profile
        confusions = (
            OCRCorruptionPatterns.VISION_API_CONFUSIONS
            if profile == OCREngineProfile.VISION_API
            else OCRCorruptionPatterns.TESSERACT_CONFUSIONS
        )
        
        # Apply token-level corruptions first (word boundaries)
        if intensity >= 0.05:
            for original, replacement in OCRCorruptionPatterns.MERGED_TOKENS.items():
                if self.random.random() < intensity * 2:
                    content = content.replace(original, replacement, 1)
        
        # Apply character-level corruptions
        result = []
        i = 0
        while i < len(content):
            char = content[i]
            
            # Check for accent stripping
            if char in OCRCorruptionPatterns.ACCENT_STRIP and self.random.random() < intensity:
                result.append(OCRCorruptionPatterns.ACCENT_STRIP[char])
                i += 1
                continue
            
            # Check for character confusion
            if char in confusions and self.random.random() < intensity:
                result.append(self.random.choice(confusions[char]))
                i += 1
                continue
            
            # Check for punctuation drops
            if char in OCRCorruptionPatterns.PUNCTUATION_DROPS and self.random.random() < intensity * 0.5:
                # Drop the punctuation
                i += 1
                continue
            
            # No corruption
            result.append(char)
            i += 1
        
        return "".join(result)
    
    def _apply_structure_corruption(
        self, 
        content: str, 
        config: SyntheticCurriculumConfig
    ) -> str:
        """Apply structure corruption based on configuration."""
        if config.structure_noise == StructureCorruption.NONE:
            return content
        
        lines = content.split("\n")
        
        if config.structure_noise == StructureCorruption.MISSING_TABLES:
            lines = [l for l in lines if not l.strip().startswith("|")]
        
        elif config.structure_noise == StructureCorruption.MALFORMED_HEADINGS:
            corrupted = []
            for line in lines:
                if line.startswith("#"):
                    if self.random.random() < 0.3:
                        line = line.replace("#", "§", 1)
                    elif self.random.random() < 0.5:
                        line = line.lstrip("#").strip()
                corrupted.append(line)
            lines = corrupted
        
        elif config.structure_noise == StructureCorruption.MIXED_LAYOUTS:
            corrupted = []
            for line in lines:
                corrupted.append(line)
                if self.random.random() < 0.1:
                    corrupted.append("")
                    corrupted.append("---")
            lines = corrupted
        
        elif config.structure_noise == StructureCorruption.SCANNED_IMAGE:
            corrupted = []
            for line in lines:
                if self.random.random() < 0.2:
                    spaces = " " * self.random.randint(1, 5)
                    line = spaces + line
                if corrupted and self.random.random() < 0.1:
                    corrupted[-1] = corrupted[-1] + " " + line
                else:
                    corrupted.append(line)
            lines = corrupted
        
        return "\n".join(lines)
    
    def _apply_jurisdiction_ambiguity(
        self, 
        content: str, 
        config: SyntheticCurriculumConfig
    ) -> str:
        """Apply jurisdiction ambiguity based on configuration."""
        if config.jurisdiction_ambiguity == JurisdictionAmbiguity.NONE:
            return content
        
        if config.jurisdiction_ambiguity == JurisdictionAmbiguity.CONFLICTING_METADATA:
            lines = content.split("\n")
            insert_idx = min(5, len(lines))
            conflicting_info = [
                "",
                f"**Note:** This curriculum may also apply to neighboring regions.",
                f"**Alternative Jurisdiction:** {self._random_jurisdiction()}",
                "",
            ]
            lines = lines[:insert_idx] + conflicting_info + lines[insert_idx:]
            return "\n".join(lines)
        
        elif config.jurisdiction_ambiguity == JurisdictionAmbiguity.MISSING_AUTHORITY:
            content = content.replace("**Country:**", "")
            content = content.replace("**Jurisdiction:**", "")
            return content
        
        elif config.jurisdiction_ambiguity == JurisdictionAmbiguity.MULTIPLE_VERSIONS:
            lines = content.split("\n")
            version_info = [
                "",
                "---",
                "",
                "## Version Information",
                "",
                "This document contains content from multiple curriculum versions:",
                "- Version 2024 (deprecated)",
                "- Version 2025 (current)",
                "- Draft Version 2026 (pending approval)",
                "",
            ]
            lines.extend(version_info)
            return "\n".join(lines)
        
        return content
    
    def _random_jurisdiction(self) -> str:
        """Generate a random fake jurisdiction name."""
        prefixes = ["North", "South", "East", "West", "Central", "Greater"]
        suffixes = ["Province", "Region", "Territory", "District", "State"]
        names = ["Avalon", "Cascadia", "Meridian", "Arcadia", "Olympus"]
        
        return f"{self.random.choice(prefixes)} {self.random.choice(names)} {self.random.choice(suffixes)}"


# =============================================================================
# TEST FIXTURES
# =============================================================================

def create_biology_test_curriculum(
    noise_level: NoiseLevel = NoiseLevel.NONE,
    structure_corruption: StructureCorruption = StructureCorruption.NONE,
    rng_seed: int | None = None,
) -> SyntheticCurriculumConfig:
    """
    Create a pre-configured Biology curriculum for testing.
    
    Contains standard topics with known ground truth.
    """
    ground_truth = GroundTruth(
        expected_grade="Grade 9",
        expected_subject="Biology",
        expected_jurisdiction="national",
        topics=[
            GroundTruthTopic(
                title="Cell Division",
                weight=TopicWeight.FOUNDATIONAL,
                learning_outcomes=[
                    "Explain the stages of mitosis",
                    "Describe the role of DNA in cell division",
                    "Compare mitosis and meiosis",
                ],
            ),
            GroundTruthTopic(
                title="Genetics",
                weight=TopicWeight.FOUNDATIONAL,
                learning_outcomes=[
                    "Define genes and chromosomes",
                    "Explain Mendelian inheritance",
                    "Predict offspring traits using Punnett squares",
                ],
            ),
            GroundTruthTopic(
                title="Evolution",
                weight=TopicWeight.STANDARD,
                learning_outcomes=[
                    "Describe natural selection",
                    "Explain adaptation",
                    "Discuss evidence for evolution",
                ],
            ),
            GroundTruthTopic(
                title="Ecology",
                weight=TopicWeight.STANDARD,
                learning_outcomes=[
                    "Define ecosystem components",
                    "Explain food chains and webs",
                    "Describe nutrient cycles",
                ],
            ),
            GroundTruthTopic(
                title="Biotechnology Applications",
                weight=TopicWeight.PERIPHERAL,
                learning_outcomes=[
                    "Discuss genetic engineering basics",
                    "Explore real-world applications",
                ],
            ),
        ],
        removed_topics=[
            GroundTruthTopic(
                title="Photosynthesis",
                weight=TopicWeight.STANDARD,
                is_present=False,
            ),
        ],
    )
    
    return SyntheticCurriculumConfig(
        synthetic_id=f"SIM-BIO-{noise_level.value.upper()}-V1",
        country="Testland",
        country_code="TL",
        jurisdiction="national",
        grade="Grade 9",
        subject="Biology",
        ocr_noise=noise_level,
        structure_noise=structure_corruption,
        ground_truth=ground_truth,
        rng_seed=rng_seed,
    )


def create_test_suite(seeded: bool = True) -> list[SyntheticCurriculumConfig]:
    """
    Create a full test suite of synthetic curricula.
    
    Args:
        seeded: If True, use deterministic seeds for reproducibility (Fix #6)
    
    Returns:
        List of configurations covering various noise levels
    """
    configs = []
    seed_base = 42 if seeded else None
    
    # Clean baseline
    configs.append(create_biology_test_curriculum(
        rng_seed=seed_base
    ))
    
    # OCR noise variations
    for i, noise in enumerate([NoiseLevel.LOW, NoiseLevel.MEDIUM, NoiseLevel.HIGH]):
        configs.append(create_biology_test_curriculum(
            noise_level=noise,
            rng_seed=(seed_base + i + 1) if seeded else None,
        ))
    
    # Structure corruption variations
    for i, corruption in enumerate(StructureCorruption):
        if corruption != StructureCorruption.NONE:
            configs.append(create_biology_test_curriculum(
                structure_corruption=corruption,
                rng_seed=(seed_base + 10 + i) if seeded else None,
            ))
    
    return configs
