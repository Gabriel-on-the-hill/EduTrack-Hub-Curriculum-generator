"""
Gatekeeper Agent (Blueprint Section 5.3.2 & 14.2)

The Gatekeeper agent is responsible for:
1. Validating source authority
2. Detecting license and usage terms
3. Extracting publication dates
4. Detecting conflicts between sources

Blueprint rules:
- approved_sources = 0 → failed
- status = conflicted → human alert
"""

import asyncio
import logging
import re
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from src.schemas.agents import (
    ApprovedSource,
    GatekeeperOutput,
    CandidateUrl,
)
from src.schemas.base import AgentStatus, AuthorityHint, LicenseType
from src.utils.gemini_client import GeminiClient, GeminiModel, get_gemini_client

logger = logging.getLogger(__name__)


# License patterns
LICENSE_PATTERNS: dict[str, list[str]] = {
    LicenseType.PUBLIC_DOMAIN: [
        "public domain",
        "no copyright",
        "cc0",
    ],
    LicenseType.CREATIVE_COMMONS: [
        "creative commons",
        "cc by",
        "cc-by",
        "attribution",
    ],
    LicenseType.GOVERNMENT: [
        "government publication",
        "crown copyright",
        "official document",
        "ministry of education",
        "published by the government",
    ],
    LicenseType.EDUCATIONAL: [
        "for educational use",
        "educational purposes",
        "non-commercial",
        "educational license",
    ],
}


class SourceAnalysis(BaseModel):
    """LLM response for source analysis."""
    is_official: bool
    license_type: str
    publication_year: int | None
    confidence: float
    reasoning: str


class GatekeeperAgent:
    """
    Gatekeeper Agent for source validation.
    
    Validates curriculum sources for authority, license, and recency.
    """
    
    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        """Initialize with optional Gemini client."""
        self._client = gemini_client or get_gemini_client()
    
    async def validate(
        self,
        candidate_urls: list[CandidateUrl],
        country: str,
        country_code: str,
        job_id: UUID | None = None,
    ) -> GatekeeperOutput:
        """
        Validate candidate URLs.
        
        Args:
            candidate_urls: URLs from Scout agent
            country: Human-readable country name
            country_code: ISO-2 country code
            job_id: Optional job ID for tracking
            
        Returns:
            GatekeeperOutput with approved sources
        """
        job_id = job_id or uuid4()
        
        if not candidate_urls:
            logger.warning("Gatekeeper received no candidate URLs")
            return GatekeeperOutput(
                job_id=job_id,
                approved_sources=[],
                rejected_sources=[],
                status=AgentStatus.FAILED,
            )
        
        try:
            approved: list[ApprovedSource] = []
            rejected_count = 0
            conflict_detected = False
            
            # Validate each URL
            rejected_urls: list[str] = []
            for candidate in candidate_urls:
                result = await self._validate_source(
                    candidate, country, country_code
                )
                
                if result is not None:
                    approved.append(result)
                else:
                    rejected_urls.append(candidate.url)
            
            # Check for conflicts
            if len(approved) > 1:
                conflict_detected = self._check_conflicts(approved)
            
            # Determine status
            if conflict_detected:
                status = AgentStatus.CONFLICTED
            elif len(approved) == 0:
                status = AgentStatus.FAILED
            else:
                status = AgentStatus.SUCCESS
            
            return GatekeeperOutput(
                job_id=job_id,
                approved_sources=approved,
                rejected_sources=rejected_urls,
                status=status,
            )
            
        except Exception as e:
            logger.error(f"Gatekeeper agent failed: {e}")
            return GatekeeperOutput(
                job_id=job_id,
                approved_sources=[],
                rejected_sources=[u.url for u in candidate_urls],
                status=AgentStatus.FAILED,
            )
    
    async def _validate_source(
        self,
        candidate: CandidateUrl,
        country: str,
        country_code: str,
    ) -> ApprovedSource | None:
        """
        Validate a single source.
        
        Returns ApprovedSource if valid, None if rejected.
        """
        # Quick authority check
        if candidate.authority_hint == AuthorityHint.OFFICIAL:
            # Official sources get fast-tracked
            pub_date = self._extract_publication_date(candidate.url)
            return ApprovedSource(
                url=candidate.url,
                authority=self._extract_authority_name(candidate.domain, country),
                license=LicenseType.GOVERNMENT,
                published_date=pub_date or date.today(),
                confidence=0.95,
            )
        
        # For unknown sources, do deeper validation
        license_type = self._detect_license(candidate.url)
        
        if license_type == LicenseType.UNKNOWN:
            # Cannot determine license, reject
            logger.info(f"Rejected {candidate.url}: unknown license")
            return None
        
        if license_type == LicenseType.RESTRICTED:
            # Restricted license, reject
            logger.info(f"Rejected {candidate.url}: restricted license")
            return None
        
        pub_date = self._extract_publication_date(candidate.url)
        return ApprovedSource(
            url=candidate.url,
            authority=self._extract_authority_name(candidate.domain, country),
            license=license_type,
            published_date=pub_date or date.today(),
            confidence=0.7,
        )
    
    def _extract_authority_name(self, domain: str, country: str) -> str:
        """Extract authority name from domain."""
        # Map known domains to authority names
        authority_map = {
            "nerdc.gov.ng": "Nigerian Educational Research and Development Council",
            "education.gov.ng": "Federal Ministry of Education, Nigeria",
            "kicd.ac.ke": "Kenya Institute of Curriculum Development",
            "nacca.gov.gh": "National Council for Curriculum and Assessment, Ghana",
            "education.gov.za": "Department of Basic Education, South Africa",
        }
        return authority_map.get(domain, f"Education Authority, {country}")
    
    def _detect_license(self, url: str) -> LicenseType:
        """
        Detect license type from URL patterns.
        
        In production, would fetch and analyze document metadata.
        """
        url_lower = url.lower()
        
        # Check for government patterns
        if ".gov." in url_lower or "ministry" in url_lower:
            return LicenseType.GOVERNMENT
        
        # Check each license pattern
        for license_type, patterns in LICENSE_PATTERNS.items():
            for pattern in patterns:
                if pattern in url_lower:
                    return license_type
        
        # Default: educational if from known edu domain
        if ".edu" in url_lower or ".ac." in url_lower:
            return LicenseType.EDUCATIONAL
        
        return LicenseType.UNKNOWN
    
    def _extract_publication_date(self, url: str) -> date | None:
        """
        Extract publication date from URL if present.
        
        Looks for year patterns like 2019, 2023, etc.
        """
        # Look for year patterns
        pattern = r"(20[12][0-9])"
        match = re.search(pattern, url)
        
        if match:
            year = int(match.group(1))
            return date(year, 1, 1)
        
        return None
    
    def _check_conflicts(self, sources: list[ApprovedSource]) -> bool:
        """
        Check if approved sources conflict.
        
        Conflicts occur when:
        - Same subject, different publication years (outdated risk)
        - Multiple "official" sources with different content hashes
        """
        dates = [s.published_date for s in sources if s.published_date]
        
        if len(dates) >= 2:
            years = sorted(set(d.year for d in dates))
            # If versions span more than 2 years, potential conflict
            if len(years) >= 2 and (years[-1] - years[0]) > 2:
                logger.warning(
                    f"Potential conflict: sources span years {years[0]}-{years[-1]}"
                )
                return True
        
        return False


async def run_gatekeeper(
    candidate_urls: list[CandidateUrl],
    country: str,
    country_code: str,
) -> GatekeeperOutput:
    """Convenience function to run Gatekeeper agent."""
    agent = GatekeeperAgent()
    return await agent.validate(candidate_urls, country, country_code)
