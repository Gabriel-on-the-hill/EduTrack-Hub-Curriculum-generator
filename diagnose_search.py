from duckduckgo_search import DDGS
from urllib.parse import urlparse
import logging

# Replicate the logic from search.py for testing
def _is_relevant(title, snippet, url, query_terms):
    text = (title + " " + snippet).lower()
    url = url.lower()
    
    # definitive negative signals
    if "wikipedia.org" in url or "census.gov" in url or "usa.gov" in url:
        return False, "Blocked Domain"
        
    educational_keywords = {
        "curriculum", "syllabus", "standards", "framework", 
        "guide", "scope and sequence", "pacing", "learning objectives",
        "lesson plan", "teacher", "student", "education", "pdf", "docs",
        "scheme of work", "grade", "year" # Added these to test if they help
    }
    
    hits = 0
    matched = []
    for w in educational_keywords:
        if w in text or w in url:
            hits += 1
            matched.append(w)
            
    # Also check for original query terms (simple check)
    q_terms = [t.lower() for t in query_terms if len(t) > 3] 
    for qt in q_terms:
         if qt in text:
             hits += 1
             matched.append(f"query({qt})")
             
    if hits >= 2:
        return True, f"Passed {hits} ({matched})"
    return False, f"Failed hits ({hits} - {matched})"

def run_diagnosis(query):
    print(f"--- Diagnosing: '{query}' ---")
    query_terms = query.split()
    
    queries = [
        f"filetype:pdf {query} curriculum",
        f"{query} curriculum standards pdf", 
        f"{query} education framework",
        f"{query} curriculum education" # Fallback
    ]
    
    with DDGS() as ddgs:
        for q in queries:
            print(f"\nSearching: {q}")
            try:
                results = list(ddgs.text(q, region="us-en", safesearch="Off", max_results=5, backend="lite"))
                if not results:
                    print("  NO RESULTS from Backend")
                    continue
                    
                for r in results:
                    url = r.get("href") or r.get("url")
                    title = r.get("title", "")
                    body = r.get("body") or r.get("snippet", "")
                    
                    is_good, reason = _is_relevant(title, body, url, query_terms)
                    status = "✅ KEEP" if is_good else f"❌ DROP ({reason})"
                    print(f"  {status} | {title[:40]}... | {url}")
            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    run_diagnosis("US Grade 8 Science Curriculum")
    run_diagnosis("UK Year 6 History Curriculum")
