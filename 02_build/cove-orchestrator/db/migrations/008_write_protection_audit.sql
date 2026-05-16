-- Migration 008: Database write protection audit + enforcement (AMP-351)
--
-- Extends migration 005 (brain_lockdown) to cover all current tables
-- including canonical schema from 007 and future pudding_labels (AMP-345).
--
-- Enforces the AMP-351 invariant: ONLY brain_writer can INSERT/UPDATE
-- on amplified_brain. The ingestion pipe is the ONLY sanctioned write path.
-- This is enforced at the PostgreSQL permission level, not just documentation.
--
-- Re-runnable: all statements use IF EXISTS / IF NOT EXISTS guards.
--
-- Run as superuser on the amplified_brain database.
--
-- Signed-by: Devon-0546 | 2026-05-16 | devin-0546725b5b9f49659ece73a55a73b27b

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════
-- 1. Ensure roles exist (idempotent, extends 005)
-- ═══════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'brain_writer') THEN
        CREATE ROLE brain_writer LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'brain_reader') THEN
        CREATE ROLE brain_reader LOGIN;
    END IF;
END
$$;

-- ═══════════════════════════════════════════════════════════════════════
-- 2. Revoke everything from PUBLIC (belt-and-braces on top of 005)
-- ═══════════════════════════════════════════════════════════════════════

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;

-- Revoke default privileges so future tables are also locked down
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM PUBLIC;

-- ═══════════════════════════════════════════════════════════════════════
-- 3. brain_reader: SELECT only on all current + future tables
-- ═══════════════════════════════════════════════════════════════════════

GRANT CONNECT ON DATABASE amplified_brain TO brain_reader;
GRANT USAGE ON SCHEMA public TO brain_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO brain_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO brain_reader;

-- ═══════════════════════════════════════════════════════════════════════
-- 4. brain_writer: SELECT + INSERT/UPDATE on sanctioned tables only
--    NO DELETE for anyone except superuser (append-only ingestion)
-- ═══════════════════════════════════════════════════════════════════════

GRANT CONNECT ON DATABASE amplified_brain TO brain_writer;
GRANT USAGE ON SCHEMA public TO brain_writer;

-- Writer can read everything
GRANT SELECT ON ALL TABLES IN SCHEMA public TO brain_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO brain_writer;

-- Writer needs sequence usage for UUID/serial columns
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO brain_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO brain_writer;

-- Sanctioned write tables (from migrations 004, 005, 007):
DO $$
DECLARE
    tbl TEXT;
    write_tables TEXT[] := ARRAY[
        'knowledge_vectors',
        'entities',
        'relationships',
        'episodes',
        'pipeline_runs',
        'ingestion_manifests',
        'audit_log',
        -- AMP-345 (pudding_labels, when migration lands):
        'pudding_labels'
    ];
BEGIN
    FOREACH tbl IN ARRAY write_tables LOOP
        IF EXISTS (
            SELECT FROM pg_tables
            WHERE schemaname = 'public' AND tablename = tbl
        ) THEN
            EXECUTE format('GRANT INSERT, UPDATE ON TABLE %I TO brain_writer', tbl);
        END IF;
    END LOOP;
END
$$;

-- ═══════════════════════════════════════════════════════════════════════
-- 5. Apache AGE schema access (for AMP-345 graph writes)
-- ═══════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_namespace WHERE nspname = 'ag_catalog') THEN
        GRANT USAGE ON SCHEMA ag_catalog TO brain_writer;
        GRANT USAGE ON SCHEMA ag_catalog TO brain_reader;
    END IF;
END
$$;

-- ═══════════════════════════════════════════════════════════════════════
-- 6. Verification query (run after migration to confirm)
-- ═══════════════════════════════════════════════════════════════════════
--
-- SELECT grantee, table_name, privilege_type
-- FROM information_schema.role_table_grants
-- WHERE table_schema = 'public'
--   AND grantee IN ('brain_writer', 'brain_reader', 'PUBLIC')
-- ORDER BY grantee, table_name, privilege_type;
--
-- Expected:
--   brain_writer: SELECT on all, INSERT+UPDATE on sanctioned tables only
--   brain_reader: SELECT on all
--   PUBLIC: nothing

COMMIT;
