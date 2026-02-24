import time
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin
import requests
from cachetools import TTLCache
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)
CACHE = TTLCache(maxsize=2000, ttl=24*3600)  # 24h cache for queries

# Configuration knobs
MAX_RESULTS_PER_QUERY = 10
SEARCH_DELAY_SECONDS = 0.6  # polite delay between internal queries
HEAD_TIMEOUT = 6
VALID_SCHEMES = {"http", "https"}
PREFERRED_TLDS = (".gov", ".edu", ".ac.uk", ".gov.uk")

def _is_official_domain(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
        return host.endswith(PREFERRED_TLDS) or any(host.endswith(t) for t in PREFERRED_TLDS)
    except Exception:
        return False

def _normalize_url(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    if raw.startswith("/"):
        # can't resolve relative without base; skip
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in VALID_SCHEMES:
        # maybe missing scheme => try https
        raw = "https://" + raw
        parsed = urlparse(raw)
        if parsed.scheme not in VALID_SCHEMES:
            return None
    return raw

def _validate_link(url: str) -> Optional[Dict]:
    """
    Lightweight HEAD-check to ensure link is usable.
    Returns dict with {url, final_url, content_type, content_length, ok}
    """
    try:
        resp = requests.head(url, allow_redirects=True, timeout=HEAD_TIMEOUT)
        final = resp.url
        status = resp.status_code
        if status != 200:
            # attempt small GET if HEAD not allowed
            respg = requests.get(url, stream=True, timeout=HEAD_TIMEOUT)
            final = respg.url
            status = respg.status_code
            resp = respg
        ctype = resp.headers.get("Content-Type", "")
        clen = resp.headers.get("Content-Length")
        return {"url": url, "final_url": final, "status": status, "content_type": ctype, "content_length": clen, "ok": status == 200}
    except Exception as e:
        logger.debug("HEAD-check failed for %s: %s", url, e)
        return None

def _expand_queries(query: str) -> List[str]:
    """
    Query expansion ordering: narrow → medium → broad
    """
    return [
        f"filetype:pdf {query} curriculum",
        f"{query} curriculum site:.gov",
        f"{query} syllabus site:.gov",
        f"{query} curriculum site:.edu",
        f"{query} curriculum standards pdf",  # Stronger keyword fallback
        f"{query} syllabus",
        f"{query} education framework" # Better than just {query}
    ]

def _is_relevant(r: dict, query_terms: List[str]) -> bool:
    """
    Heuristic to reject generic 'US Info' pages.
    Result must contain at least one educational keyword or specific query usage.
    """
    text = (r.get("title", "") + " " + r.get("snippet", "")).lower()
    url = r.get("url", "").lower()
    
    # definitive negative signals
    if "wikipedia.org" in url or "census.gov" in url or "usa.gov" in url:
        # exceptions: specific education subdomains (ignored for now for simplicity)
        return False
        
    educational_keywords = {
        "curriculum", "syllabus", "standards", "framework", 
        "guide", "scope and sequence", "pacing", "learning objectives",
        "lesson plan", "teacher", "student", "education", "pdf", "docs"
    }
    
    # Check for intersection
    hits = 0
    for w in educational_keywords:
        if w in text or w in url:
            hits += 1
            
    # Also check for original query terms (simple check)
    q_terms = [t.lower() for t in query_terms if len(t) > 3] # ignore 'us', 'uk'
    for qt in q_terms:
         if qt in text:
             hits += 1
             
    return hits >= 2 # Require at least 2 relevant signals (e.g. "science" + "curriculum")

def search_web(query: str, max_results: int = 10, region: str = "us-en", use_cache: bool = True) -> List[Dict]:
    """
    Returns list of results: [{'title','url','snippet','domain','official_hint','final_url','content_type'}]
    """
    cache_key = f"search:{region}:{query}:{max_results}"
    if use_cache and cache_key in CACHE:
        return CACHE[cache_key]

    collected = []
    seen = set()
    ddgs = DDGS()
    queries = _expand_queries(query)
    
    query_terms = query.split()

    for q in queries:
        # Respect small delay between attempts
        time.sleep(SEARCH_DELAY_SECONDS)
        try:
            # DDGS.text returns generator; here we use the client
            for r in ddgs.text(q, region=region, safesearch="Off", timelimit=5, max_results=max_results):
                # r is a dict with keys that vary: 'href' or 'url' etc.
                url_raw = r.get("href") or r.get("url") or r.get("link") or None
                url = _normalize_url(url_raw)
                if not url:
                    continue
                if url in seen:
                    continue
                seen.add(url)
                
                # Check relevance BEFORE HEAD check to save time
                temp_res = {
                    "title": r.get("title") or "",
                    "snippet": r.get("body") or r.get("snippet") or "",
                    "url": url
                }
                if not _is_relevant(temp_res, query_terms):
                    continue

                # lightweight validation (HEAD)
                info = _validate_link(url)
                if not info or not info.get("ok"):
                    # reject bad or non-200 links; but keep HTML pages if OK
                    continue

                domain = urlparse(info["final_url"]).hostname or ""
                result = {
                    "title": temp_res["title"],
                    "url": url,
                    "snippet": temp_res["snippet"],
                    "domain": domain,
                    "official_hint": _is_official_domain(url),
                    "final_url": info["final_url"],
                    "content_type": info.get("content_type")
                }
                collected.append(result)
                if len(collected) >= max_results:
                    break
        except Exception as e:
            logger.warning("Search provider call failed on query '%s': %s", q, e)
        if len(collected) >= max_results:
            break

    # If still empty, optionally return looser results without HEAD-checks (configurable)
    if not collected:
        # try very broad search without filetype or head-check (allow HTML preview)
        time.sleep(SEARCH_DELAY_SECONDS)
        fallback_q = f"{query} curriculum education" # Ensure we don't just search "US"
        try:
            for r in ddgs.text(fallback_q, region=region, max_results=max_results):
                url_raw = r.get("href") or r.get("url")
                url = _normalize_url(url_raw)
                if not url or url in seen:
                    continue
                    
                # Basic check only
                if "wikipedia" in url: continue
                
                collected.append({
                    "title": r.get("title", ""), 
                    "url": url, 
                    "snippet": r.get("body",""), 
                    "domain": urlparse(url).hostname or ""
                })
                if len(collected) >= max_results:
                    break
        except Exception:
            pass

    # Prioritize official domains (.gov etc.)
    collected = sorted(collected, key=lambda r: (not r.get("official_hint"), r.get("domain", "")))[:max_results]

    if use_cache:
        CACHE[cache_key] = collected

    return collected
