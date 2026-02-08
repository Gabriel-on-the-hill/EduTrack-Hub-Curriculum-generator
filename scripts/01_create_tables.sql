-- EduTrack Database Schema
-- Run this in Supabase SQL Editor (or any PostgreSQL)

-- 1. Curricula Table
CREATE TABLE IF NOT EXISTS curricula (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country TEXT NOT NULL,
    country_code TEXT NOT NULL,
    jurisdiction_level TEXT NOT NULL DEFAULT 'national',
    jurisdiction_name TEXT,
    grade TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    confidence_score DECIMAL(3,2) DEFAULT 1.0,
    source_url TEXT,
    source_authority TEXT,
    last_verified TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Competencies Table
CREATE TABLE IF NOT EXISTS competencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    curriculum_id UUID NOT NULL REFERENCES curricula(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    learning_outcomes TEXT[],
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_competencies_curriculum ON competencies(curriculum_id);
CREATE INDEX IF NOT EXISTS idx_curricula_country ON curricula(country_code);

-- 4. Enable Row Level Security (optional but recommended)
ALTER TABLE curricula ENABLE ROW LEVEL SECURITY;
ALTER TABLE competencies ENABLE ROW LEVEL SECURITY;

-- Allow public read access (for demo purposes)
CREATE POLICY "Public read access" ON curricula FOR SELECT USING (true);
CREATE POLICY "Public read access" ON competencies FOR SELECT USING (true);

COMMENT ON TABLE curricula IS 'Verified curriculum metadata from official sources';
COMMENT ON TABLE competencies IS 'Atomic learning objectives within each curriculum';
