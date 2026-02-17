import hashlib

def compute_text_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
