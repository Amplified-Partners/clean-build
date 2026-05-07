---
name: ingestion-pipeline
description: How to operate the Amplified ingestion pipeline (Classify → Orchestrate → Write) on Beast. Covers CLI, env vars, checkpoint DB, FalkorDB write patterns, and dependencies.
---

# Ingestion Pipeline — Operational Guide

## Location

`02_build/pipeline/` in the clean-build repo.

## Architecture

```
Scan → Classify (Ollama llama3.1:8b) → Orchestrate (Research Pipe, opt-in) → Write (FalkorDB + Qdrant)
```

Each item is checkpointed per-stage in SQLite (WAL mode). Pipeline is crash-safe and resumable.

## CLI Usage (on Beast)

```bash
# SSH to Beast
ssh -i ~/.ssh/beastkey root@135.181.161.131

# Navigate to corpus
cd /opt/amplified/vault/store_b_clean

# Classify only (safe first run)
python -m pipeline.cli run . --classify-only --workers 12

# Full pipeline (classify + orchestrate + write)
python -m pipeline.cli run .

# Resume after crash
python -m pipeline.cli resume .

# Check progress
python -m pipeline.cli status .

# Retry failed items from dead letter queue
python -m pipeline.cli retry-dlq .
```

## Beast Infrastructure

| Service | Address | Notes |
|---------|---------|-------|
| Beast SSH | root@135.181.161.131 | Key: `$beastkey` env var, write to `~/.ssh/beastkey` |
| Ollama | 172.18.0.12:11434 | Models: llama3.1:8b (classifier), nomic-embed-text (embedder) |
| FalkorDB | 172.18.0.22:6379 | Graph: `business_knowledge` |
| Qdrant | localhost:6333 | Collection: `amplified_knowledge` |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|--------|
| `OLLAMA_URL` | `http://172.18.0.12:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `llama3.1:8b` | Classification model |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Qdrant embedding model |
| `FALKORDB_HOST` | `172.18.0.22` | FalkorDB Redis host |
| `FALKORDB_PORT` | `6379` | FalkorDB Redis port |
| `FALKORDB_GRAPH` | `business_knowledge` | Graph name |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `QDRANT_COLLECTION` | `amplified_knowledge` | Collection name |
| `ORCHESTRATOR_ENABLED` | `0` | Set `1` to enable research pipe (needs Anthropic billing, AMP-142) |
| `WRITER_BATCH_SIZE` | `50` | UNWIND batch size for FalkorDB |
| `WRITER_VERIFY_RETRIES` | `3` | Verify-retry attempts per batch |

## FalkorDB Write Pattern

UNWIND-batched MERGE with verify-and-retry (from apds_labeller_v2.2, AMP-128):
1. Build batch of 50 items as Cypher map literals
2. `UNWIND` + `MERGE` in a single Cypher call
3. Read-back count to verify all doc_ids landed
4. If missing: retry batch up to 3 times
5. If still missing: items go to DLQ for per-doc retry

## Checkpoint Database

SQLite at `{corpus_dir}/.pipeline/pipeline.db`:
- `pipeline_items` — per-file state (pending → classifying → classified → orchestrating → orchestrated → writing → written)
- `dlq` — dead letter queue with attempt counter
- `run_meta` — run history with timestamps

## Research Pipe (AMP-157)

5 stages in `02_build/scripts/`:
1. `intake_research_pipe.py` — accept question, extract metadata
2. `interpreter_research_pipe.py` — neutralise language, detect assumptions (needs Anthropic)
3. `curator1_research_pipe.py` — design multi-pass search strategy (Ollama fallback available)
4. `search_research_pipe.py` — execute searches (Exa + arXiv + SearXNG)
5. `curator2_research_pipe.py` — sufficiency check + synthesis (needs Anthropic)

Disabled by default. Set `ORCHESTRATOR_ENABLED=1` once Anthropic billing is resolved (AMP-142).

## Dependencies

- `pydantic` — data models (required)
- `pytest` — tests (dev only)
- `redis` — FalkorDB client (optional, dry-run if unavailable)
- `qdrant-client` — Qdrant client (optional, dry-run if unavailable)

## Running Tests

```bash
cd 02_build
python -m pytest pipeline/tests/ -v
```

21 tests covering checkpoint store, DLQ, models, and classification logic.

## Corpus State (2026-05-07)

- 21,380 total files in `store_b_clean`
- 1,616 already classified (~19,764 remaining)
- Boilerplate files (license, readme, changelog, etc.) are auto-skipped
- Already-classified files (frontmatter with `dimensions:`) are auto-skipped

## Tickets

- AMP-155: PUDDING Classification Scale-up
- AMP-156: Memory Store Writer (FalkorDB + Qdrant)
- AMP-157: Orchestrator Integration
- AMP-158: Pipeline Orchestration & Reliability

---
*Devon-220b | 2026-05-07 | session devin-220b8b8d17044c9f85ac8ec5eb4154b5*
