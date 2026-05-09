-- Migration 006: Compound Design Schema — Brain Backend Wiring (AMP-280)
-- Adds relational tables, pgvector HNSW indexes, and AGE graph for the
-- Compound Design system (memory-write / memory-recall for design artifacts).
--
-- Target database: amplified_brain (via BRAIN_DSN)
-- Depends on: 005_brain_lockdown.sql (role grants pattern)
-- Signed-by: Devon-a81b | 2026-05-09 | devin-a81b5692e70143b99b2d55f8a9ccf81b

-- ─── Extensions (idempotent) ──────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ─── Relational Tables ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS design_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    artifact_type TEXT NOT NULL,        -- 'component' | 'layout' | 'pattern' | 'token' | 'composition'
    phase TEXT NOT NULL,                 -- 'discover' | 'define' | 'develop' | 'deliver'
    description TEXT,
    content JSONB DEFAULT '{}',         -- Flexible payload (CSS vars, specs, rationale, etc.)
    tags TEXT[] DEFAULT '{}',
    embedding vector(384),
    source TEXT,                         -- Origin: 'plugin:compound-design' | 'manual' | 'polish-sync'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS design_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    category TEXT NOT NULL,             -- 'spacing' | 'typography' | 'color' | 'motion' | 'layout' | 'interaction'
    description TEXT,
    rationale TEXT,                      -- Why this pattern exists
    constraints JSONB DEFAULT '{}',     -- Hard rules the pattern enforces
    examples JSONB DEFAULT '[]',        -- Array of example usages
    embedding vector(384),
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    domain TEXT NOT NULL,               -- 'accessibility' | 'performance' | 'aesthetics' | 'usability' | 'brand'
    summary TEXT NOT NULL,
    evidence JSONB DEFAULT '{}',        -- Citations, links, data points
    confidence REAL CHECK (confidence >= 0 AND confidence <= 1),
    embedding vector(384),
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pudding_concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    bridge_a TEXT NOT NULL,             -- First domain concept
    bridge_b TEXT NOT NULL,             -- Second domain concept
    mechanism TEXT,                      -- How A connects to B
    pudding_score REAL,                 -- Emergence score E = (B × D × N) / R
    domain_distance REAL,
    confidence_band TEXT,               -- 'PROVEN' | 'VALID' | 'HYPOTHESIS' | 'INSUFFICIENT'
    embedding vector(384),
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── pgvector HNSW Indexes ────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_design_artifacts_embedding
    ON design_artifacts USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_design_patterns_embedding
    ON design_patterns USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_research_findings_embedding
    ON research_findings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_pudding_concepts_embedding
    ON pudding_concepts USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ─── Supplementary Indexes ────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_design_artifacts_type ON design_artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_design_artifacts_phase ON design_artifacts(phase);
CREATE INDEX IF NOT EXISTS idx_design_patterns_category ON design_patterns(category);
CREATE INDEX IF NOT EXISTS idx_research_findings_domain ON research_findings(domain);
CREATE INDEX IF NOT EXISTS idx_pudding_concepts_band ON pudding_concepts(confidence_band);

-- ─── Apache AGE Graph ─────────────────────────────────────────────────────────
-- AGE extension must be installed (Antigravity compiled it into cove-postgres).

CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create the compound_design graph (idempotent check)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'compound_design') THEN
        PERFORM create_graph('compound_design');
    END IF;
END $$;

-- Create vertex labels for graph nodes
SELECT create_vlabel('compound_design', 'Artifact');
SELECT create_vlabel('compound_design', 'Pattern');
SELECT create_vlabel('compound_design', 'Research');
SELECT create_vlabel('compound_design', 'Pudding');
SELECT create_vlabel('compound_design', 'Concept');

-- Create edge labels (5 relationship types)
SELECT create_elabel('compound_design', 'INFORMS');
SELECT create_elabel('compound_design', 'DERIVES_FROM');
SELECT create_elabel('compound_design', 'CONTRADICTS');
SELECT create_elabel('compound_design', 'BRIDGES_TO');
SELECT create_elabel('compound_design', 'VALIDATED_BY');

-- Reset search_path
SET search_path = "$user", public;

-- ─── Role Grants ──────────────────────────────────────────────────────────────
-- Follow pattern from 005_brain_lockdown.sql

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'brain_writer') THEN
        GRANT INSERT, UPDATE ON TABLE design_artifacts TO brain_writer;
        GRANT INSERT, UPDATE ON TABLE design_patterns TO brain_writer;
        GRANT INSERT, UPDATE ON TABLE research_findings TO brain_writer;
        GRANT INSERT, UPDATE ON TABLE pudding_concepts TO brain_writer;
        GRANT USAGE ON SCHEMA ag_catalog TO brain_writer;
    END IF;

    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'brain_reader') THEN
        GRANT SELECT ON TABLE design_artifacts TO brain_reader;
        GRANT SELECT ON TABLE design_patterns TO brain_reader;
        GRANT SELECT ON TABLE research_findings TO brain_reader;
        GRANT SELECT ON TABLE pudding_concepts TO brain_reader;
        GRANT USAGE ON SCHEMA ag_catalog TO brain_reader;
    END IF;
END $$;

-- ─── Updated_at Triggers ──────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_compound_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER design_artifacts_updated_at BEFORE UPDATE ON design_artifacts
    FOR EACH ROW EXECUTE FUNCTION update_compound_updated_at();

CREATE TRIGGER design_patterns_updated_at BEFORE UPDATE ON design_patterns
    FOR EACH ROW EXECUTE FUNCTION update_compound_updated_at();

CREATE TRIGGER research_findings_updated_at BEFORE UPDATE ON research_findings
    FOR EACH ROW EXECUTE FUNCTION update_compound_updated_at();

CREATE TRIGGER pudding_concepts_updated_at BEFORE UPDATE ON pudding_concepts
    FOR EACH ROW EXECUTE FUNCTION update_compound_updated_at();
