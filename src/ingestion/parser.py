import fitz
import hashlib
import requests
import tempfile
from bs4 import BeautifulSoup

import os


MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB limit

def download_file(url: str) -> str:
    response = requests.get(url, timeout=30, stream=True)
    response.raise_for_status()

    # Check Content-Length header first if available
    content_length = response.headers.get('Content-Length')
    if content_length and int(content_length) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File at {url} exceeds the 20MB size limit (reported {content_length} bytes)")

    suffix = ".pdf" if "pdf" in response.headers.get("content-type", "") else ".html"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    
    downloaded_size = 0
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            downloaded_size += len(chunk)
            if downloaded_size > MAX_FILE_SIZE_BYTES:
                tmp.close()
                os.unlink(tmp.name)
                raise ValueError(f"File at {url} exceeds the 20MB size limit during download")
            tmp.write(chunk)
            
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
