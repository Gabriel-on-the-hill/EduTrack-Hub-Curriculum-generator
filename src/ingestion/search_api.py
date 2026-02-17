from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from cachetools import TTLCache, cached
from slowapi import Limiter
from slowapi.util import get_remote_address
import requests
from src.ingestion.search import search_web
from src.ingestion.gatekeeper import infer_authority

router = APIRouter()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Caching: 500 queries, 24h TTL
search_cache = TTLCache(maxsize=500, ttl=86400)

class SearchRequest(BaseModel):
    query: str
    max_results: int = 10

@router.post("/api/ingest/search")
@limiter.limit("5/minute")
def search(request: Request, req: SearchRequest):
    # Check cache manually or use decorator
    if req.query in search_cache:
        return {"results": search_cache[req.query]}

    results = search_web(req.query, req.max_results)

    annotated = []
    for r in results:
        annotated.append({
            **r,
            "authority_hint": infer_authority(r["url"])
        })

    search_cache[req.query] = annotated
    return {"results": annotated}


@router.get("/api/ingest/preview")
@limiter.limit("10/minute")
def preview(request: Request, url: str):
    try:
        # User-agent to avoid immediate blocking
        headers = {"User-Agent": "Mozilla/5.0 (compatible; EduTrackBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type")
        content_length = resp.headers.get("Content-Length")

        # Read small snippet safely
        snippet = ""
        try:
            # Read first 4KB
            chunk = next(resp.iter_content(chunk_size=4096), b"")
            snippet = chunk.decode("utf-8", errors="ignore")[:2000]
        except Exception:
            pass
        finally:
            resp.close()

        return {
            "content_type": content_type,
            "content_length": content_length,
            "preview_snippet": snippet[:1000]
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
