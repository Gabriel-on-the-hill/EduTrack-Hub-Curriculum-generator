from duckduckgo_search import DDGS
from typing import List, Dict
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

def duckduckgo_search(query: str, max_results: int = 10) -> List[Dict]:
    results = []
    try:
        with DDGS() as ddgs:
            # Try backend="lite" with US region
            for r in ddgs.text(query, max_results=max_results, backend="lite", region="us-en"):
                url = r.get("href") or r.get("url")
                if not url:
                    continue
                    
                parsed = urlparse(url)
                results.append({
                    "title": r.get("title"),
                    "url": url,
                    "snippet": r.get("body") or r.get("snippet"),
                    "domain": parsed.netloc,
                })
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        
    return results
