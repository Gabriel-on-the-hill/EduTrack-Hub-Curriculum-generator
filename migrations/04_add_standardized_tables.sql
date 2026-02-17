-- migrations/04_add_standardized_tables.sql
CREATE TABLE IF NOT EXISTS standardized_competencies (
  standardized_id TEXT PRIMARY KEY, /* SQLite uses TEXT for UUID */
  curriculum_id TEXT,
  original_text TEXT,
  standardized_text TEXT,
  action_verb TEXT,
  content TEXT,
  context TEXT,
  bloom_level TEXT,
  complexity_level TEXT,
  source_chunk_id TEXT,
  extraction_confidence REAL,
  llm_provenance TEXT, /* JSON stored as TEXT in SQLite */
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS competency_metadata (
  id TEXT PRIMARY KEY,
  standardized_id TEXT REFERENCES standardized_competencies(standardized_id) ON DELETE CASCADE,
  subject TEXT,
  grade_level TEXT,
  domain TEXT,
  confidence_score REAL,
  tags TEXT, /* JSON list stored as TEXT */
  llm_provenance TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_standardized_curriculum ON standardized_competencies(curriculum_id);
