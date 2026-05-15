---
title: Canonical Data Architecture
date: 2026-05-14
version: 1
status: authoritative
changelog:
  - version: 1
    date: 2026-05-14
    change: Initial commit — one engine, three capabilities.
    signed_by: Devon-4c30
---

# Canonical Data Architecture

## The Stack

| Layer | Technology | Purpose |
|-------|-----------|----------|
| Relational | PostgreSQL | All structured data — CRM, tenants, Business Brain, telemetry, finance, compliance, audit |
| Graph | PostgreSQL + Apache AGE | Entity relationships, knowledge graph, PUDDING recipe graphs. Same PostgreSQL instance — no separate process. |
| Vector | PostgreSQL + pgvector (HNSW indexing) | Semantic search, embeddings, vault content retrieval, semantic cache. Same PostgreSQL instance. |

**One database engine. Three capabilities. No separate processes.**

## Deprecated (do NOT use in new work)

| Old | Replaced by | Reason |
|-----|------------|--------|
| FalkorDB (standalone graph DB, port 6379) | PostgreSQL + Apache AGE | Stability issues — AMP-141, AMP-139, clean-build PRs #54/#55 |
| Qdrant (standalone vector DB, ports 6333-6334) | PostgreSQL + pgvector (HNSW) | Stability issues — same incident chain |

## Terminology (locked)

- **"the Russian maths"** = HNSW algorithm (Hierarchical Navigable Small World) by Yury Malkov & Dmitry Yashunin (2016). The vector indexing algorithm used by pgvector.
- **pgvector** = PostgreSQL extension for vector similarity search. NOT Qdrant. NOT a separate service.
- **Apache AGE** = PostgreSQL extension for graph (openCypher queries). NOT FalkorDB. NOT Neo4j. NOT a separate process.
- **HNSW** = the indexing algorithm. O(log n) query time. A mathematical algorithm, not a product.

## Agent Rules

1. Do NOT provision, reference, or depend on FalkorDB or Qdrant in new work.
2. All new graph work → Apache AGE (openCypher syntax inside PostgreSQL).
3. All new vector/embedding work → pgvector (HNSW index).
4. Existing FalkorDB/Qdrant code is legacy — mark it, migrate it, or flag it.

## Migration Status

All migrations are **Planned**, not yet executed:

| Source | Target | Scale |
|--------|--------|-------|
| FalkorDB → AGE | 9,000 nodes across 4 graphs | Pending |
| Qdrant → pgvector | 57,434 embeddings (384-dim) | Pending |
| Token-proxy semantic cache (Qdrant `llm_cache`) → pgvector table | ~unknown | Pending |

## Current State (Beast)

PostgreSQL instance: `cove-postgres:5432`
- Database: `amplified_brain`
- pgvector: active (225K rows, 384-dim HNSW embeddings)
- Apache AGE: active (1 graph: `compound_design`)
- Entities: 54K rows
- Relationships: 34K rows

FalkorDB container: still running (legacy, read-only use during migration)
Qdrant container: deprecated, to be decommissioned

---

*Devon-4c30 | 2026-05-14 | session devin-4c30b171b2074de7842c99f77e5093c1*
