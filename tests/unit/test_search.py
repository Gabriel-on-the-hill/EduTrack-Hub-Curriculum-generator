
import pytest
from unittest.mock import patch, MagicMock
from src.ingestion import search as search_mod

# Sample fake DDG hits with different shapes
DDG_RESULTS_MIX = [
    {"title": "Title A", "href": "https://example.gov/docA.pdf", "body": "Official doc A"},
    {"title": "Title B", "url": "http://example.edu/docB", "body": "Edu doc"},
    {"title": "Title C", "link": "example.org/pageC", "body": "Third party"},
]

def make_ddgs_mock(results):
    class FakeDDGS:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False
        def text(self, q, region=None, safesearch=None, timelimit=None, max_results=None, backend=None):
            # emulate generator of dicts
            for r in results:
                yield r
    return FakeDDGS()

# HEAD-check helper: returns 200 for gov/edu, 404 for others
def fake_head_ok(url, allow_redirects=True, timeout=6):
    m = MagicMock()
    if "example.gov" in url or "example.edu" in url:
        m.status_code = 200
        m.url = url
        m.headers = {"Content-Type": "application/pdf", "Content-Length": "1024"}
    else:
        m.status_code = 404
        m.url = url
        m.headers = {}
    return m

@patch("src.ingestion.search.DDGS")
@patch("src.ingestion.search.requests.head")
def test_search_filters_and_normalizes(mock_head, mock_ddgs):
    # arrange
    mock_ddgs.return_value = make_ddgs_mock(DDG_RESULTS_MIX)
    mock_head.side_effect = fake_head_ok

    # act
    results = search_mod.search_web("test query", max_results=5, region="us-en", use_cache=False)

    # assert: only gov and edu survive HEAD-check; org gets filtered
    urls = [r["url"] for r in results]
    assert any("example.gov" in u for u in urls)
    assert any("example.edu" in u for u in urls)
    assert not any("example.org" in u for u in urls)

@patch("src.ingestion.search.DDGS")
@patch("src.ingestion.search.requests.head")
def test_dedupe_and_final_url_priority(mock_head, mock_ddgs):
    # simulate DDG returning same URL twice (different shapes)
    dup_results = [
        {"title":"X","href":"https://example.gov/doc.pdf","body":"a"},
        {"title":"X dup","url":"https://example.gov/doc.pdf","body":"a-dup"}
    ]
    mock_ddgs.return_value = make_ddgs_mock(dup_results)
    mock_head.side_effect = fake_head_ok

    results = search_mod.search_web("dup", max_results=5, region="us-en", use_cache=False)
    assert len(results) == 1  # deduped

@patch("src.ingestion.search.DDGS")
@patch("src.ingestion.search.requests.head")
def test_cache_hits_and_misses(mock_head, mock_ddgs, tmp_path):
    # simple cache test: call twice and ensure DDGS called once
    mock_ddgs.return_value = make_ddgs_mock(DDG_RESULTS_MIX)
    mock_head.side_effect = fake_head_ok

    q = "cache-test"
    # first call: fills cache
    r1 = search_mod.search_web(q, max_results=5, region="us-en", use_cache=True)
    # patch DDGS to raise if called again
    mock_ddgs.side_effect = Exception("DDG should not be called on cached query")
    r2 = search_mod.search_web(q, max_results=5, region="us-en", use_cache=True)
    assert r1 == r2

@patch("src.ingestion.search.DDGS")
@patch("src.ingestion.search.requests.head")
@patch("src.ingestion.search.requests.get")
def test_head_check_handles_head_fail_then_get(mock_get, mock_head, mock_ddgs):
    # simulate HEAD returns non-200 but GET returns 200
    def head_then_get(url, allow_redirects=True, timeout=6):
        m = MagicMock()
        m.status_code = 405  # method not allowed
        return m
    def get_ok(url, stream=True, timeout=6):
        m = MagicMock()
        m.status_code = 200
        m.url = url
        m.headers = {"Content-Type":"text/html"}
        return m

    # patch DDGS to return a url
    mock_ddgs.return_value = make_ddgs_mock([{"title":"G","href":"https://example.gov/g","body":"g"}])
    mock_head.side_effect = head_then_get
    mock_get.side_effect = get_ok
    
    results = search_mod.search_web("head-get", max_results=5, region="us-en", use_cache=False)
    assert results and results[0]["url"].startswith("https://")
