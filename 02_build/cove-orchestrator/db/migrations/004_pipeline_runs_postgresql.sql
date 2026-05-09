-- Ingestion pipeline_runs — PostgreSQL canonical data layer
-- Run order: 004 (depends on 001)
-- Replaces Qdrant/FalkorDB column names with PostgreSQL-native equivalents.
-- See 00_authority/DATA_ARCHITECTURE.md for canonical architecture.
--
-- Signed-by: Devon-973e | 2026-05-08 | devin-973ed35fae1b4b44a52594bcb53b3f0a

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT,

    -- Stage 1: Unified ingestion
    ingestion_new_files INT DEFAULT 0,
    ingestion_total_unique INT DEFAULT 0,
    ingestion_elapsed FLOAT DEFAULT 0,

    -- Stage 2: PUDDING extraction
    pudding_labelled INT DEFAULT 0,
    pudding_skipped INT DEFAULT 0,
    pudding_errors INT DEFAULT 0,

    -- Stage 3: Memory store writer (amplified_brain PostgreSQL)
    memory_pg_vectors INT DEFAULT 0,
    memory_pg_entities INT DEFAULT 0,
    memory_errors INT DEFAULT 0,

    -- Completion
    completed_at TEXT,
    status TEXT DEFAULT 'running',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created ON pipeline_runs(created_at);
