import fitz
import hashlib
import requests
import tempfile
from bs4 import BeautifulSoup
from typing import Tuple
import os


def download_file(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    suffix = ".pdf" if "pdf" in response.headers.get("content-type", "") else ".html"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(response.content)
    tmp.close()
    return tmp.name


def parse_pdf(path: str) -> str:
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()


def parse_html(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
        return soup.get_text(separator="\n").strip()


def compute_checksum(path: str) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        sha256.update(f.read())
    return sha256.hexdigest()
