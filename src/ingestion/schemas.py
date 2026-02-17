from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime


class ParsedDocument(BaseModel):
    source_url: HttpUrl
    raw_text: str
    snapshot_path: Optional[str]
    checksum: str


class ExtractedCompetency(BaseModel):
    title: str
    description: str
    learning_outcomes: List[str] = []
    source_chunk_id: str


class IngestionResult(BaseModel):
    status: str  # success | rejected | pending_manual_review
    authority_level: Optional[str]
    license_tag: Optional[str]
    competencies: List[ExtractedCompetency] = []
    processed_at: datetime
