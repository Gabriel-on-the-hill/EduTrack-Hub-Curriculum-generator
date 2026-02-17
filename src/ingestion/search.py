from typing import List
from .search_provider import duckduckgo_search


def expand_query(query: str) -> List[str]:
    return [
        f"{query} filetype:pdf",
        f"{query} curriculum site:.gov",
        f"{query} syllabus site:.edu",
    ]


def search_web(query: str, max_results: int = 10):
    queries = expand_query(query)
    results = []

    # Simple sequential execution (could be parallelized)
    for q in queries:
        try:
            results.extend(duckduckgo_search(q, max_results=max_results))
        except Exception:
            continue

    # Deduplicate by URL
    seen = set()
    unique = []
    for r in results:
        url = r.get("url")
        if url and url not in seen:
            seen.add(url)
            unique.append(r)

    return unique[:max_results]
