from duckduckgo_search import DDGS
from typing import List, Dict
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

def duckduckgo_search(query: str, max_results: int = 10) -> List[Dict]:
    results = []
    try:
        with DDGS() as ddgs:
            # text() returns an iterator
            for r in ddgs.text(query, max_results=max_results):
                parsed = urlparse(r.get("href"))
                results.append({
                    "title": r.get("title"),
                    "url": r.get("href"),
                    "snippet": r.get("body"),
                    "domain": parsed.netloc,
                })
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        
    return results
