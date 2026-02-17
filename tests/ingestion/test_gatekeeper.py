# tests/ingestion/test_gatekeeper.py
from src.ingestion.gatekeeper import validate_document

def test_validate_document_ministry():
    decision = validate_document("https://education.gov.uk/syllabus", "Ministry content Copyright 2026")
    assert decision["authority_level"] == "high"
    assert decision["status"] == "approved"

def test_validate_document_restricted():
    decision = validate_document("https://example.com", "All rights reserved 2026")
    assert decision["license_tag"] == "restricted"
    assert decision["status"] == "pending_manual_review"

def test_validate_document_outdated():
    decision = validate_document("https://edu.gov", "Published in 2010")
    assert decision["status"] == "rejected"
    assert decision["reason"] == "outdated"
