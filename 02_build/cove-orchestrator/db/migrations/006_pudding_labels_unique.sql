-- Migration 006: Add UNIQUE constraint on pudding_labels(entity_id, pudding_code)
-- Required for ON CONFLICT DO NOTHING to prevent duplicate labels on re-runs.
-- Signed-by: Devon-973e | 2026-05-09 | devin-973ed35fae1b4b44a52594bcb53b3f0a

CREATE UNIQUE INDEX IF NOT EXISTS idx_pudding_labels_entity_code
    ON pudding_labels (entity_id, pudding_code);
