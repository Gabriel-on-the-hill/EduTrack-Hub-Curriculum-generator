from __future__ import annotations
from pydantic import BaseModel, Field, AnyUrl, validator
from typing import List, Optional, Dict
from datetime import datetime
from uuid import uuid4

# --- Existing Models ---
class SourceInfo(BaseModel):
    url: str
    title: str
    file_type: str  # "pdf" or "html"
    downloaded_at: datetime = Field(default_factory=datetime.utcnow)
    checksum: str  # sha256 of file content
    snapshot_path: str  # local path to stored file

class CompetencyChunk(BaseModel):
    chunk_id: str
    text: str
    page_number: Optional[int] = None
    section_header: Optional[str] = None
    chunk_metadata: Optional[Dict] = None  # RENAMED from metadata to avoid conflict

class ExtractedCompetency(BaseModel):
    title: str
    description: str
    learning_outcomes: List[str] = []
    source_chunk_id: str

class ExtractorOutput(BaseModel):
    competencies: List[ExtractedCompetency]
    raw_text_summary: Optional[str] = None
    
# --- Phase 3 Models ---
class StandardizedCompetency(BaseModel):
    standardized_id: str = Field(default_factory=lambda: str(uuid4()))
    original_text: str
    standardized_text: str
    action_verb: Optional[str]
    content: Optional[str]
    context: Optional[str] = None
    bloom_level: Optional[str] = None  # Remember, Understand, Apply, Analyze, Evaluate, Create
    complexity_level: Optional[str] = None  # Low, Medium, High
    source_chunk_id: str  # must reference existing chunk
    extraction_confidence: float = Field(..., ge=0.0, le=1.0)
    llm_provenance: Optional[Dict] = None  # {model:..., prompt_hash:..., response_raw:...}
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("source_chunk_id")
    def require_chunk(cls, v):
        if not v:
            raise ValueError("source_chunk_id is required for grounding")
        return v

class CompetencyMetadata(BaseModel):
    standardized_id: str  # link to StandardizedCompetency.standardized_id
    subject: Optional[str] = None
    grade_level: Optional[str] = None
    domain: Optional[str] = None
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    llm_provenance: Optional[Dict] = None
