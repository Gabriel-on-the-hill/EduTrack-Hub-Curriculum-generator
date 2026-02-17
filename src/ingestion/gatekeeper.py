import re
from datetime import datetime


def infer_authority(url: str) -> str:
    if ".gov" in url:
        return "high"
    if ".edu" in url:
        return "medium"
    return "low"


def extract_license(text: str) -> str:
    if re.search(r"creative commons", text, re.I):
        return "creative_commons"
    if re.search(r"all rights reserved", text, re.I):
        return "restricted"
    return "unknown"


def freshness_check(text: str) -> bool:
    years = re.findall(r"(20\d{2})", text)
    if not years:
        return True
    latest = max(map(int, years))
    return datetime.now().year - latest <= 5


def validate_document(url: str, text: str) -> dict:
    authority = infer_authority(url)
    license_tag = extract_license(text)
    fresh = freshness_check(text)

    if not fresh:
        return {"status": "rejected", "reason": "outdated"}

    if license_tag == "restricted":
        return {
            "status": "pending_manual_review",
            "authority_level": authority,
            "license_tag": license_tag
        }

    return {
        "status": "approved",
        "authority_level": authority,
        "license_tag": license_tag,
    }
