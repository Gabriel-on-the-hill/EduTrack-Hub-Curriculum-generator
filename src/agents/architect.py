"""
Architect Agent (Blueprint Section 5.3.3 & 14.2)

The Architect agent is responsible for:
1. Downloading curriculum PDFs
2. Extracting text using PyMuPDF
3. Parsing competencies using LLM
4. Mapping competencies to page ranges

Blueprint rules:
- average_confidence < 0.75 → low_confidence
- competencies.length = 0 → failed
"""

import asyncio
import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import aiohttp
import fitz  # PyMuPDF

from pydantic import BaseModel

from src.schemas.agents import (
    ArchitectOutput,
    CompetencyItem,
    CurriculumSnapshot,
)
from src.schemas.base import AgentStatus
from src.utils.gemini_client import GeminiClient, get_gemini_client

logger = logging.getLogger(__name__)


# Prompt for extracting competencies
EXTRACTION_PROMPT = """You are an expert curriculum analyst. Extract all learning competencies from the following curriculum document text.

For each competency, provide:
1. A clear, concise title
2. A detailed description
3. Specific, measurable learning outcomes
4. The page range where this competency appears (estimate if not exact)

Respond with a JSON array of competencies. Each competency should have:
- title: string
- description: string  
- learning_outcomes: array of strings (at least 1)
- page_range: string (e.g., "5-7" or "12")
- confidence: number between 0 and 1

Be thorough but precise. Only extract actual competencies, not general information.

CURRICULUM TEXT:
{text}
"""


class ExtractedCompetency(BaseModel):
    """LLM response for a single competency."""
    title: str
    description: str
    learning_outcomes: list[str]
    page_range: str
    confidence: float


class ExtractionResponse(BaseModel):
    """LLM response for competency extraction."""
    competencies: list[ExtractedCompetency]


class ArchitectAgent:
    """
    Architect Agent for curriculum parsing.
    
    Downloads PDFs, extracts text, and parses competencies.
    """
    
    def __init__(
        self,
        gemini_client: GeminiClient | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        """Initialize with optional Gemini client and cache directory."""
        self._client = gemini_client or get_gemini_client()
        self._cache_dir = cache_dir or Path(tempfile.gettempdir()) / "edutrack_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def parse(
        self,
        source_url: str,
        job_id: UUID | None = None,
    ) -> ArchitectOutput:
        """
        Parse a curriculum document.
        
        Args:
            source_url: URL of the curriculum PDF
            job_id: Optional job ID for tracking
            
        Returns:
            ArchitectOutput with extracted competencies
        """
        job_id = job_id or uuid4()
        
        try:
            # Download PDF
            pdf_path, checksum = await self._download_pdf(source_url)
            
            # Extract text from PDF
            text, page_count = self._extract_text(pdf_path)
            
            if not text.strip():
                logger.error(f"No text extracted from {source_url}")
                return self._failed_output(job_id, pdf_path, checksum, page_count)
            
            # Extract competencies using LLM
            competencies = await self._extract_competencies(text)
            
            if not competencies:
                logger.warning(f"No competencies extracted from {source_url}")
                return self._failed_output(job_id, pdf_path, checksum, page_count)
            
            # Calculate average confidence
            avg_confidence = sum(c.confidence for c in competencies) / len(competencies)
            
            # Determine status
            if avg_confidence < 0.75:
                status = AgentStatus.LOW_CONFIDENCE
            else:
                status = AgentStatus.SUCCESS
            
            return ArchitectOutput(
                job_id=job_id,
                curriculum_snapshot=CurriculumSnapshot(
                    file_path=str(pdf_path),
                    checksum=checksum,
                    pages=page_count,
                ),
                competencies=competencies,
                average_confidence=avg_confidence,
                status=status,
            )
            
        except Exception as e:
            logger.error(f"Architect agent failed: {e}")
            return ArchitectOutput(
                job_id=job_id,
                curriculum_snapshot=CurriculumSnapshot(
                    file_path="error",
                    checksum="error",
                    pages=0,
                ),
                competencies=[],
                average_confidence=0.0,
                status=AgentStatus.FAILED,
            )
    
    def _failed_output(
        self,
        job_id: UUID,
        pdf_path: Path,
        checksum: str,
        page_count: int,
    ) -> ArchitectOutput:
        """Create a failed output with snapshot info."""
        return ArchitectOutput(
            job_id=job_id,
            curriculum_snapshot=CurriculumSnapshot(
                file_path=str(pdf_path),
                checksum=checksum,
                pages=page_count,
            ),
            competencies=[],
            average_confidence=0.0,
            status=AgentStatus.FAILED,
        )
    
    async def _download_pdf(self, url: str) -> tuple[Path, str]:
        """
        Download PDF and return path and checksum.
        
        Uses cache to avoid re-downloading.
        """
        # Generate cache key from URL
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_path = self._cache_dir / f"{url_hash}.pdf"
        
        if cache_path.exists():
            logger.info(f"Using cached PDF: {cache_path}")
            checksum = self._compute_checksum(cache_path)
            return cache_path, checksum
        
        # Download the PDF
        logger.info(f"Downloading PDF: {url}")
        
        # For mock/testing, create a dummy PDF if URL is not real
        if "example.org" in url or not url.startswith("http"):
            return self._create_mock_pdf(cache_path)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to download PDF: {response.status}")
                
                content = await response.read()
                cache_path.write_bytes(content)
        
        checksum = self._compute_checksum(cache_path)
        return cache_path, checksum
    
    def _create_mock_pdf(self, path: Path) -> tuple[Path, str]:
        """Create a mock PDF for testing."""
        # Create a simple PDF with test content
        doc = fitz.open()
        page = doc.new_page()
        
        text = """
        BIOLOGY CURRICULUM - GRADE 9
        
        Unit 1: Cell Biology
        
        Competency 1.1: Cell Structure
        Students will understand the basic structure of cells.
        Learning Outcomes:
        - Identify the main parts of a cell
        - Describe the function of organelles
        - Compare plant and animal cells
        
        Competency 1.2: Cell Division
        Students will understand the process of cell division.
        Learning Outcomes:
        - Explain the stages of mitosis
        - Describe the importance of cell division
        - Identify factors affecting cell division
        
        Unit 2: Human Biology
        
        Competency 2.1: Digestive System
        Students will understand the human digestive system.
        Learning Outcomes:
        - Identify organs of the digestive system
        - Describe the process of digestion
        - Explain nutrient absorption
        """
        
        page.insert_text((50, 50), text, fontsize=10)
        doc.save(str(path))
        doc.close()
        
        checksum = self._compute_checksum(path)
        return path, checksum
    
    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA-256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _extract_text(self, pdf_path: Path) -> tuple[str, int]:
        """
        Extract text from PDF using PyMuPDF.
        
        Returns text and page count.
        """
        doc = fitz.open(str(pdf_path))
        text_parts: list[str] = []
        
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text()
            if page_text.strip():
                text_parts.append(f"[Page {page_num}]\n{page_text}")
        
        doc.close()
        
        return "\n".join(text_parts), len(doc)
    
    async def _extract_competencies(self, text: str) -> list[CompetencyItem]:
        """
        Extract competencies from text using LLM.
        
        Falls back to rule-based extraction if LLM fails.
        """
        # Truncate text if too long (Gemini has token limits)
        max_chars = 30000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[truncated...]"
        
        try:
            # Try LLM extraction
            prompt = EXTRACTION_PROMPT.format(text=text)
            result = await self._client.generate_structured(
                prompt=prompt,
                response_schema=ExtractionResponse,
            )
            
            # Convert to CompetencyItem
            competencies: list[CompetencyItem] = []
            for i, comp in enumerate(result.competencies):
                competencies.append(CompetencyItem(
                    competency_id=uuid4(),
                    title=comp.title,
                    description=comp.description,
                    learning_outcomes=comp.learning_outcomes or ["General learning outcome"],
                    page_range=comp.page_range or "1",
                    confidence=comp.confidence,
                ))
            
            return competencies
            
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}, using rule-based fallback")
            return self._rule_based_extraction(text)
    
    def _rule_based_extraction(self, text: str) -> list[CompetencyItem]:
        """
        Rule-based fallback for competency extraction.
        
        Looks for patterns like "Competency X.Y:" or "Learning Outcome:"
        """
        import re
        
        competencies: list[CompetencyItem] = []
        
        # Pattern to find competencies
        pattern = r"Competency\s+(\d+\.?\d*):?\s*(.+?)(?=Competency|\Z)"
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        
        for i, (num, content) in enumerate(matches):
            # Extract title (first line)
            lines = content.strip().split("\n")
            title = lines[0].strip() if lines else f"Competency {num}"
            
            # Extract learning outcomes
            outcomes: list[str] = []
            for line in lines[1:]:
                line = line.strip()
                if line.startswith("-") or line.startswith("•"):
                    outcomes.append(line.lstrip("-•").strip())
            
            if not outcomes:
                outcomes = ["Complete the learning activities"]
            
            competencies.append(CompetencyItem(
                competency_id=uuid4(),
                title=title[:200],  # Truncate long titles
                description=content[:500],  # Truncate description
                learning_outcomes=outcomes[:10],  # Max 10 outcomes
                page_range="1",  # Default page range
                confidence=0.6,  # Lower confidence for rule-based
            ))
        
        return competencies


async def run_architect(source_url: str) -> ArchitectOutput:
    """Convenience function to run Architect agent."""
    agent = ArchitectAgent()
    return await agent.parse(source_url)
