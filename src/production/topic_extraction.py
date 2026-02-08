"""
Topic Extraction (Phase 5)

Extracts topics from generated markdown for delta computation.
Makes metrics meaningful (not empty lists).
"""

import re
from typing import List


def extract_topics(markdown: str) -> List[str]:
    """
    Extract topic headers from markdown content.
    
    Args:
        markdown: Generated markdown content
        
    Returns:
        List of normalized topic strings (lowercase, stripped)
    """
    # Match markdown headers (# Header, ## Header, etc.)
    headers = re.findall(r"^#+\s+(.*)", markdown, flags=re.MULTILINE)
    
    # Normalize: lowercase and strip
    topics = [h.strip().lower() for h in headers if h.strip()]
    
    return topics


def extract_topics_with_level(markdown: str) -> List[dict]:
    """
    Extract topics with their heading level.
    
    Returns:
        List of dicts with 'level' (int) and 'text' (str)
    """
    pattern = r"^(#+)\s+(.*)"
    matches = re.findall(pattern, markdown, flags=re.MULTILINE)
    
    return [
        {"level": len(m[0]), "text": m[1].strip().lower()}
        for m in matches
        if m[1].strip()
    ]
