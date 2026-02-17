-- migrations/sqlite_03_add_ingestion_columns.sql
-- SQLite-friendly migration for local development

ALTER TABLE curricula ADD COLUMN source_url TEXT;
ALTER TABLE curricula ADD COLUMN snapshot_path TEXT;
ALTER TABLE curricula ADD COLUMN checksum TEXT;
ALTER TABLE curricula ADD COLUMN authority_level TEXT;
ALTER TABLE curricula ADD COLUMN license_tag TEXT;
ALTER TABLE curricula ADD COLUMN ingested_at DATETIME;
ALTER TABLE curricula ADD COLUMN extraction_confidence REAL;
ALTER TABLE curricula ADD COLUMN status TEXT DEFAULT 'pending';

CREATE TABLE IF NOT EXISTS curriculum_chunks (
  chunk_id TEXT PRIMARY KEY,
  curriculum_id TEXT,
  page_range TEXT,
  text TEXT,
  extraction_method TEXT,
  confidence REAL,
  checksum TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
  job_id TEXT PRIMARY KEY,
  source_url TEXT,
  requested_by TEXT,
  status TEXT,
  created_at DATETIME,
  last_updated DATETIME,
  job_payload TEXT,
  decision_reason TEXT
);
