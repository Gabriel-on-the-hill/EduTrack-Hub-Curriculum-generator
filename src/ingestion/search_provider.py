"""
Simple concrete search provider using duckduckgo-search if available,
otherwise returns empty list.

Returns list of dicts: {"url":..., "title":..., "snippet":..., "domain":..., "official_hint":bool}
"""

from typing import List, Dict
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    from duckduckgo_search import ddg
    HAVE_DDG = True
except Exception:
    HAVE_DDG = False

def _is_official(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        host = host.lower()
        return host.endswith(".gov") or host.endswith(".edu") or host.endswith(".gov.uk") or host.endswith(".ac.uk")
    except Exception:
        return False

def duckduckgo_search(query: str, max_results: int = 10) -> List[Dict]:
    results = []
    if not HAVE_DDG:
        logger.warning("duckduckgo-search package not available. Install duckduckgo-search for real searches.")
        return results
    try:
        raw = ddg(query, max_results=max_results)
        for item in raw or []:
            url = item.get("href") or item.get("url")
            title = item.get("title") or ""
            snippet = item.get("body") or item.get("snippet") or ""
            results.append({
                "url": url,
                "title": title,
                "snippet": snippet,
                "domain": (urlparse(url).hostname if url else ""),
                "official_hint": _is_official(url) if url else False
            })
    except Exception as e:
         logger.error(f"DuckDuckGo search failed: {e}")
         
    return results
