-- Migration 009: Research pipe tables
--
-- Tracks research jobs from intake through verified closure.
-- No job reaches a terminal state without closure evidence.
--
-- Depends on: 008_brain_curator_tables.sql
-- Run as superuser on the amplified_brain database.
--
-- Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════
-- 1. Research jobs
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE research_jobs (
    job_id          TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'intake_open',
    lift_result     JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_rj_state ON research_jobs (state);
CREATE INDEX idx_rj_created ON research_jobs (created_at DESC);

-- ═══════════════════════════════════════════════════════════════════════
-- 2. Research questions
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE research_questions (
    question_id     TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL REFERENCES research_jobs(job_id),
    text            TEXT NOT NULL,
    answer          TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'open',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rq_job ON research_questions (job_id);
CREATE INDEX idx_rq_status ON research_questions (status);

-- ═══════════════════════════════════════════════════════════════════════
-- 3. Evidence items
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE research_evidence_items (
    evidence_id     TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL REFERENCES research_jobs(job_id),
    source          TEXT NOT NULL,
    content         TEXT NOT NULL,
    epistemic_tier  TEXT NOT NULL DEFAULT 'INTUITED',
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_rei_job ON research_evidence_items (job_id);
CREATE INDEX idx_rei_tier ON research_evidence_items (epistemic_tier);

-- ═══════════════════════════════════════════════════════════════════════
-- 4. Claim-evidence links
-- ═══════════════════════════════════════════════════════════════════════

CREATE TABLE claim_evidence_links (
    link_id         TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL REFERENCES research_jobs(job_id),
    claim           TEXT NOT NULL,
    evidence_id     TEXT NOT NULL REFERENCES research_evidence_items(evidence_id),
    relationship    TEXT NOT NULL DEFAULT 'supports',
    strength        REAL NOT NULL DEFAULT 0.5,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cel_job ON claim_evidence_links (job_id);
CREATE INDEX idx_cel_evidence ON claim_evidence_links (evidence_id);

COMMIT;
