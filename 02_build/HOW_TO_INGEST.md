---
title: How to Ingest Content into the Business Brain
version: 1
signed_by: Devon-973e | 2026-05-08 | devin-973ed35fae1b4b44a52594bcb53b3f0a
---

# How to Ingest Content into the Business Brain

## Quick Start

1. Drop raw files into `/opt/amplified/raw-mac-dumps` on Beast (135.181.161.131)
2. The pipeline runs automatically via Temporal, or trigger manually (see below)
3. Content flows through 3 stages and lands in `amplified_brain` PostgreSQL

## The 3-Stage Pipeline

```
raw-mac-dumps → [Stage 1: Ingest] → store_b_clean → [Stage 2: PUDDING Label] → [Stage 3: Write to PostgreSQL]
```

### Stage 1: Unified Ingestion (`run_unified_ingestion`)

- **Input:** `/opt/amplified/raw-mac-dumps` (any file type)
- **Output:** `/opt/amplified/archive/store_b_clean` (deduplicated, attributed)
- **What it does:**
  - Hashes every file (SHA-256) for deduplication
  - Skips files already in `seen_hashes.json`
  - Renames files with radical naming: `{date}_{topic}_{author}_{hash}{ext}`
  - Adds ingestion attribution to JSON files
  - Runs in parallel (8 workers default)

### Stage 2: PUDDING Extraction (`run_pudding_extraction`)

- **Input:** `store_b_clean` (`.md` and `.txt` files)
- **Output:** Same files, with PUDDING 2026 Taxonomy YAML frontmatter injected
- **What it does:**
  - Sends content to Anthropic Claude Haiku for taxonomy labelling
  - Extracts: concepts, sources, recipes, signals, domains
  - Assigns 4-character PUDDING codes (`WHAT.HOW.SCALE.TIME`)
  - Skips files that already have PUDDING frontmatter
- **Requires:** `ANTHROPIC_API_KEY` environment variable with active billing
- **Known blocker:** Anthropic billing exhausted as of 2026-05-06 (AMP-142). Stage 2 will fail until billing is topped up. Stages 1 and 3 work independently.

### Stage 3: Memory Store Writer (`write_to_memory_stores`)

- **Input:** `store_b_clean` (PUDDING-labelled `.md` files)
- **Output:** Rows in `amplified_brain` PostgreSQL database
- **What it does:**
  - Reads files with PUDDING frontmatter (`lbd_attribution` + `PUDDING` markers)
  - Upserts into `knowledge_vectors` table (content + metadata, pgvector/HNSW)
  - Upserts into `entities` table (one entity per concept extracted)
  - Inserts into `pudding_labels` table (PUDDING taxonomy codes per entity)
  - All IDs are deterministic (SHA-256 of file path or concept name) — re-runs are idempotent
- **Connects to:** `amplified_brain` database on Beast PostgreSQL (`cove-postgres` container)

## Where Files Go

| What | Path on Beast |
|------|---------------|
| Raw drops (input) | `/opt/amplified/raw-mac-dumps` |
| Clean archive (stage 1 output) | `/opt/amplified/archive/store_b_clean` |
| Seen hashes (dedup index) | `/opt/amplified/archive/store_b_clean/seen_hashes.json` |
| PUDDING ledger (V3 audit trail) | `/opt/amplified/vault-ingestion-progress/v3_skipped.jsonl` |

## How to Query the Database

Connect to `amplified_brain` on Beast PostgreSQL:

```bash
# From Beast host
docker exec -it cove-postgres psql -U cove -d amplified_brain

# Or remotely (if port 5432 is exposed)
psql postgresql://brain_reader:<password>@135.181.161.131:5432/amplified_brain
```

### Useful queries

```sql
-- Count everything
SELECT 'entities' AS tbl, count(*) FROM entities
UNION ALL SELECT 'relationships', count(*) FROM relationships
UNION ALL SELECT 'knowledge_vectors', count(*) FROM knowledge_vectors
UNION ALL SELECT 'pudding_labels', count(*) FROM pudding_labels;

-- Find entities by name (text search)
SELECT name, entity_type, summary
FROM entities
WHERE name ILIKE '%marketing%'
LIMIT 20;

-- Vector similarity search (pgvector/HNSW)
-- Requires a 384-dim query vector; example uses a zero vector placeholder
SELECT id, source, content_snippet
FROM knowledge_vectors
ORDER BY embedding <=> '[0,0,...,0]'::vector(384)
LIMIT 10;

-- PUDDING labels for a concept
SELECT e.name, p.pudding_code, p.what_dim, p.how_dim, p.scale_dim, p.time_dim
FROM pudding_labels p
JOIN entities e ON e.id = p.entity_id
WHERE e.name ILIKE '%discovery%';

-- Graph traversal: find related entities
SELECT e2.name AS related, r.relation_type, r.summary
FROM relationships r
JOIN entities e1 ON e1.id = r.source_id
JOIN entities e2 ON e2.id = r.target_id
WHERE e1.name = 'Some Entity Name';
```

### MCP access

Two MCP containers provide structured access:

- **brain-mcp-writer** (port 8080): Full read/write via MCP protocol
- **brain-mcp-readonly** (port 8081): Read-only queries via MCP protocol

## Manual Trigger

The pipeline is orchestrated by Temporal. To trigger manually via the pre-ingestion script:

```bash
# On Beast, run the V3 pre-ingestion pipe
docker exec -it cove-worker python /opt/amplified/pre_ingestion_pipe_v3.py \
  --source /opt/amplified/raw-mac-dumps \
  --clean /opt/amplified/archive/store_b_clean \
  --author Ewan_Sair
```

## Current State (2026-05-08)

| Table | Rows | Notes |
|-------|------|-------|
| entities | 53,959 | With 384-dim embeddings + HNSW index |
| relationships | 34,488 | With embeddings |
| knowledge_vectors | 57,434 | Migrated from Qdrant, HNSW indexed |
| pudding_labels | 0 | Empty — awaiting Anthropic billing top-up (AMP-142) |
| episodes | 4,257 | |
| episode_entities | 59,192 | |

## Blockers

- **AMP-142:** Anthropic billing exhausted — Stage 2 (PUDDING labelling) will not run until topped up. Stages 1 and 3 are unaffected.
- **FalkorDB/Qdrant:** Deprecated. Do not use. Stage 3 now writes to PostgreSQL directly.
