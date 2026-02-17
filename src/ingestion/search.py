import requests
from typing import List


def expand_query(query: str) -> List[str]:
    return [
        f"{query} site:.gov filetype:pdf",
        f"{query} site:.edu filetype:pdf",
        f"{query} curriculum filetype:pdf",
    ]


def basic_search(query: str) -> List[str]:
    """
    Placeholder: returns URLs.
    Replace with Serper/Playwright in production.
    """
    # Deliberately minimal
    return []
