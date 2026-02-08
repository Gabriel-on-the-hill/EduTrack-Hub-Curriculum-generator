"""
Scout Agent (Blueprint Section 5.3.1 & 14.2)

The Scout agent is responsible for:
1. Generating targeted search queries
2. Searching for official curriculum sources
3. Ranking and filtering candidate URLs
4. Detecting authority hints (official vs unknown)

Blueprint rules:
- queries.length ≤ 5
- candidate_urls.length ≥ 1 OR status = failed
"""

import asyncio
import logging
import re
from typing import Any
from uuid import UUID, uuid4

import aiohttp

from src.schemas.agents import CandidateUrl, ScoutOutput
from src.schemas.base import AgentStatus, AuthorityHint
from src.utils.gemini_client import GeminiClient, GeminiModel, get_gemini_client

logger = logging.getLogger(__name__)


# Known official education domains by country
OFFICIAL_DOMAINS: dict[str, list[str]] = {
    "NG": [
        "nerdc.gov.ng",
        "education.gov.ng",
        "waec.org.ng",
    ],
    "KE": [
        "kicd.ac.ke",
        "education.go.ke",
        "knec.ac.ke",
    ],
    "GH": [
        "nacca.gov.gh",
        "moe.gov.gh",
    ],
    "ZA": [
        "education.gov.za",
        "dbe.gov.za",
    ],
    "US": [
        ".gov",
        "corestandards.org",
    ],
    "GB": [
        "gov.uk",
        "education.gov.uk",
    ],
    "CA": [
        ".edu.on.ca",
        ".edu.bc.ca",
        ".edu.ab.ca",
    ],
}

# University and higher education domains (global)
UNIVERSITY_DOMAINS: list[str] = [
    # Generic academic domains
    ".edu",
    ".ac.uk",
    ".ac.za",
    ".edu.ng",
    ".edu.au",
    # Open courseware platforms
    "ocw.mit.edu",
    "coursera.org",
    "edx.org",
    "khanacademy.org",
    # Major universities
    "harvard.edu",
    "stanford.edu",
    "ox.ac.uk",
    "cam.ac.uk",
]


class ScoutAgent:
    """
    Scout Agent for curriculum source discovery.
    
    Uses search to find official curriculum documents.
    """
    
    def __init__(self, gemini_client: GeminiClient | None = None) -> None:
        """Initialize with optional Gemini client."""
        self._client = gemini_client or get_gemini_client()
    
    async def search(
        self,
        country: str,
        country_code: str,
        grade: str,
        subject: str,
        job_id: UUID | None = None,
    ) -> ScoutOutput:
        """
        Search for curriculum sources.
        
        Args:
            country: Human-readable country name
            country_code: ISO-2 country code
            grade: Grade level (e.g., "Grade 9")
            subject: Subject name (e.g., "Biology")
            job_id: Optional job ID for tracking
            
        Returns:
            ScoutOutput with candidate URLs
        """
        job_id = job_id or uuid4()
        
        try:
            # Generate search queries
            queries = self._generate_queries(country, grade, subject)
            
            # Execute searches
            all_urls: list[CandidateUrl] = []
            for query in queries:
                urls = await self._execute_search(query, country_code)
                all_urls.extend(urls)
            
            # Deduplicate and rank
            ranked_urls = self._rank_and_deduplicate(all_urls, country_code)
            
            # Check if we found anything
            if len(ranked_urls) == 0:
                logger.warning(f"Scout found no URLs for {country} {grade} {subject}")
                return ScoutOutput(
                    job_id=job_id,
                    queries=queries,
                    candidate_urls=[],
                    status=AgentStatus.FAILED,
                )
            
            return ScoutOutput(
                job_id=job_id,
                queries=queries,
                candidate_urls=ranked_urls[:10],  # Top 10
                status=AgentStatus.SUCCESS,
            )
            
        except Exception as e:
            logger.error(f"Scout agent failed: {e}")
            return ScoutOutput(
                job_id=job_id,
                queries=self._generate_queries(country, grade, subject),
                candidate_urls=[],
                status=AgentStatus.FAILED,
            )
    
    def _generate_queries(
        self,
        country: str,
        grade: str,
        subject: str,
    ) -> list[str]:
        """
        Generate search queries for curriculum discovery.
        
        Blueprint: Max 5 queries.
        Handles both K-12 and university-level curricula.
        """
        grade_lower = grade.lower()
        
        # Detect if this is a university-level request
        is_university = any(term in grade_lower for term in [
            "university", "college", "bachelor", "master", "phd",
            "undergraduate", "graduate", "bsc", "msc", "ba", "ma",
            "year 1", "year 2", "year 3", "year 4",
            "freshman", "sophomore", "junior", "senior",
            "101", "201", "301", "401",  # Course numbering
        ])
        
        if is_university:
            # University-specific queries
            queries = [
                f"{subject} {grade} syllabus PDF",
                f"{subject} course outline {grade} university",
                f"{subject} curriculum {grade} learning outcomes",
                f"{grade} {subject} course description syllabus",
                f"MIT OpenCourseWare {subject} OR Coursera {subject} syllabus",
            ]
        else:
            # K-12 queries
            queries = [
                f"{country} {grade} {subject} curriculum official PDF",
                f"{country} {grade} {subject} syllabus ministry of education",
                f"official {subject} curriculum {grade} {country} filetype:pdf",
                f"{country} national curriculum {subject} {grade}",
                f"{subject} learning outcomes {grade} {country} education",
            ]
        
        return queries[:5]  # Enforce max 5
    
    async def _execute_search(
        self,
        query: str,
        country_code: str,
    ) -> list[CandidateUrl]:
        """
        Execute a search query.
        
        Note: In production, this would use a search API like SerpAPI.
        For now, we return mock results based on known patterns.
        """
        # Mock implementation - in production, use actual search API
        # This simulates finding official curriculum sources
        
        mock_results = self._get_mock_results(query, country_code)
        return mock_results
    
    def _get_mock_results(
        self,
        query: str,
        country_code: str,
    ) -> list[CandidateUrl]:
        """
        Get mock search results for testing.
        
        In production, replace with actual search API.
        """
        # Simulated results based on country and query content
        query_lower = query.lower()
        results: list[CandidateUrl] = []
        
        if country_code == "NG":
            if "biology" in query_lower:
                results.append(CandidateUrl(
                    url="https://nerdc.gov.ng/curriculum/biology-jss3-2019.pdf",
                    domain="nerdc.gov.ng",
                    rank=1,
                    authority_hint=AuthorityHint.OFFICIAL,
                ))
            if "chemistry" in query_lower or "science" in query_lower:
                results.append(CandidateUrl(
                    url="https://nerdc.gov.ng/curriculum/chemistry-ss1-2019.pdf",
                    domain="nerdc.gov.ng",
                    rank=2,
                    authority_hint=AuthorityHint.OFFICIAL,
                ))
        elif country_code == "KE":
            results.append(CandidateUrl(
                url="https://kicd.ac.ke/curriculum/secondary/science-8-4-4.pdf",
                domain="kicd.ac.ke",
                rank=1,
                authority_hint=AuthorityHint.OFFICIAL,
            ))
        elif country_code == "GH":
            results.append(CandidateUrl(
                url="https://nacca.gov.gh/curriculum/science-jhs.pdf",
                domain="nacca.gov.gh",
                rank=1,
                authority_hint=AuthorityHint.OFFICIAL,
            ))
        
        # Add generic result if no specific matches
        if not results:
            results.append(CandidateUrl(
                url=f"https://education.example.org/curriculum/{country_code.lower()}.pdf",
                domain="education.example.org",
                rank=1,
                authority_hint=AuthorityHint.UNKNOWN,
            ))
        
        return results
    
    def _detect_authority(self, url: str, country_code: str) -> AuthorityHint:
        """
        Detect if a URL is from an official source.
        
        Checks against known official domains and university domains.
        """
        domain = self._extract_domain(url)
        
        # Check country-specific official domains
        official_domains = OFFICIAL_DOMAINS.get(country_code, [])
        for official in official_domains:
            if official in domain:
                return AuthorityHint.OFFICIAL
        
        # Check university domains (global)
        for uni_domain in UNIVERSITY_DOMAINS:
            if uni_domain in domain:
                return AuthorityHint.OFFICIAL
        
        # Check for common government patterns
        if ".gov." in domain or "/gov/" in url:
            return AuthorityHint.OFFICIAL
        
        # Check for academic patterns
        if ".edu" in domain or ".ac." in domain:
            return AuthorityHint.OFFICIAL
        
        return AuthorityHint.UNKNOWN
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        match = re.search(r"https?://([^/]+)", url)
        return match.group(1) if match else url
    
    def _rank_and_deduplicate(
        self,
        urls: list[CandidateUrl],
        country_code: str,
    ) -> list[CandidateUrl]:
        """
        Rank and deduplicate URLs.
        
        Priority:
        1. Official sources
        2. PDF files
        3. Recency (if detectable)
        """
        seen_urls: set[str] = set()
        unique: list[CandidateUrl] = []
        
        for url in urls:
            if url.url not in seen_urls:
                seen_urls.add(url.url)
                # Re-detect authority
                url.authority_hint = self._detect_authority(url.url, country_code)
                unique.append(url)
        
        # Sort: official first, then by original rank
        unique.sort(
            key=lambda u: (
                0 if u.authority_hint == AuthorityHint.OFFICIAL else 1,
                u.rank,
            )
        )
        
        # Reassign ranks
        for i, url in enumerate(unique, start=1):
            url.rank = i
        
        return unique


async def run_scout(
    country: str,
    country_code: str,
    grade: str,
    subject: str,
) -> ScoutOutput:
    """Convenience function to run Scout agent."""
    agent = ScoutAgent()
    return await agent.search(country, country_code, grade, subject)
