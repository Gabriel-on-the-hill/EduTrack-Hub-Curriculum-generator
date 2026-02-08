"""
Data Access Layer (Phase 5)

Fetches verified data from the Truth Layer.
NO EMPTY LISTS - raises if data not found.

This module queries the actual Supabase/Postgres tables.
"""

from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.production.errors import CompetencyNotFoundError


def fetch_competencies(session: Session, curriculum_id: str) -> list[dict]:
    """
    Fetch atomic competencies for the given curriculum.
    
    Queries the `competencies` table (as defined in src/schemas/curriculum.py).
    
    Args:
        session: Read-only database session
        curriculum_id: ID of the curriculum (UUID string)
        
    Returns:
        List of competency dicts with 'id', 'text', 'title' keys
        
    Raises:
        CompetencyNotFoundError: If no competencies found (NO EMPTY LISTS)
    """
    # Query competencies table
    # Schema: id, curriculum_id, title, description, learning_outcomes, etc.
    result = session.execute(
        text("""
            SELECT id, title, description 
            FROM competencies 
            WHERE curriculum_id = :cid
            ORDER BY id
        """),
        {"cid": curriculum_id}
    )
    
    rows = result.fetchall()
    
    if not rows:
        raise CompetencyNotFoundError(curriculum_id)
    
    # Return in format expected by GroundingVerifier: {'id': str, 'text': str}
    return [
        {
            "id": str(row[0]),
            "title": row[1],
            "text": row[2]  # 'description' becomes 'text' for grounding
        }
        for row in rows
    ]


def fetch_curriculum_mode(session: Session, curriculum_id: str) -> str:
    """
    Determine content mode (k12 or university) from curriculum.
    
    Queries the `curricula` table to get jurisdiction_level.
    
    Args:
        session: Read-only database session
        curriculum_id: ID of the curriculum
        
    Returns:
        "k12" or "university"
    """
    result = session.execute(
        text("""
            SELECT jurisdiction_level, source_authority
            FROM curricula 
            WHERE id = :cid
        """),
        {"cid": curriculum_id}
    )
    
    row = result.fetchone()
    if not row:
        return "k12"  # Default to stricter mode if not found
    
    jurisdiction_level = (row[0] or "").lower()
    source_authority = (row[1] or "").lower()
    
    # University detection logic:
    # - Explicit "university" in jurisdiction
    # - .edu domain in source authority
    # - Known university authorities
    if "university" in jurisdiction_level:
        return "university"
    
    if ".edu" in source_authority:
        return "university"
    
    # Known university indicators
    university_keywords = ["university", "college", "institute of technology", "polytechnic"]
    if any(kw in source_authority for kw in university_keywords):
        return "university"
    
    return "k12"


def fetch_curriculum_metadata(session: Session, curriculum_id: str) -> dict[str, Any]:
    """
    Fetch full curriculum metadata for provenance.
    
    Returns:
        Dict with curriculum details for governance checks
    """
    result = session.execute(
        text("""
            SELECT 
                id, country, country_code, 
                jurisdiction_level, jurisdiction_name,
                grade, subject, status, 
                confidence_score, source_url, source_authority
            FROM curricula 
            WHERE id = :cid
        """),
        {"cid": curriculum_id}
    )
    
    row = result.fetchone()
    if not row:
        return {}
    
    return {
        "id": str(row[0]),
        "country": row[1],
        "country_code": row[2],
        "jurisdiction_level": row[3],
        "jurisdiction_name": row[4],
        "grade": row[5],
        "subject": row[6],
        "status": row[7],
        "confidence_score": float(row[8]) if row[8] else None,
        "source_url": row[9],
        "source_authority": row[10]
    }
