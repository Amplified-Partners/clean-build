---
title: The Amplified Brain — Architecture & Physical Map
date: 2026-05-14
version: 1
status: authoritative now
supersedes: Linear doc "The Amplified Brain Architecture (Where the Brain Lives)" (c655776f3baa)
signed-by:
  - Devon-3386 | 2026-05-14 | devin-338635b0d3cd4a868f1cf7e7fcb8d461
---

<!-- markdownlint-disable-file MD013 -->

# The Amplified Brain — Architecture & Physical Map

Source of truth for the physical and conceptual layout of the Amplified Partners intelligence engine. Defines where the Brain lives, what it is made of, and how every agent (Devon, Cursor, Cassian, Antigravity) interacts with it.

**Cursor access: full read/write.** Cursor may read this file for architectural context and propose edits to keep it current. Changes follow normal PR workflow (`00_authority/PR_WORKFLOW.md`).

---

## 1. What the Brain Is

The Amplified Brain is a living, multi-layer intelligence engine that processes, stores, and connects the firm's sovereign business knowledge. It is not a single folder or a local script — it is a set of capabilities running inside a unified database engine on dedicated hardware.

Three functional layers:

| Layer | Capability | Technology | Purpose |
|-------|-----------|------------|---------|
| **Right Hemisphere** (Meaning) | Vector search | PostgreSQL + **pgvector** (HNSW indexing) | Semantic similarity over all vault content. 384-dim embeddings. The "Russian maths" — Malkov & Yashunin (2016). |
| **Left Hemisphere** (Logic) | Graph traversal | PostgreSQL + **Apache AGE** (openCypher) | Entity relationships, knowledge graph, PUDDING recipe graphs. Same PostgreSQL instance — no separate process. |
| **Nervous System** (Action) | Orchestration | **Temporal** + Cove workers | Fires webhooks, schedules pipelines, dictates agent execution. |

**One database engine. Three capabilities. No separate processes for graph or vector.**

### Deprecated components (do NOT use in new work)

| Old | Replaced by | Status |
|-----|------------|--------|
| FalkorDB (standalone graph DB, port 6379) | PostgreSQL + Apache AGE | Containers still running (legacy data); migration planned — 9,000 nodes across 4 graphs. |
| Qdrant (standalone vector DB, ports 6333-6334) | PostgreSQL + pgvector (HNSW) | Containers still running (legacy data); migration planned — 57,434 embeddings (384-dim). |

Source: Canonical Data Architecture decision (2026-05-08). FalkorDB and Qdrant stability issues documented in AMP-141, AMP-139, clean-build PRs #54/#55.

---

## 2. Where the Brain Lives (The Sovereign Engine)

**Physical location:** Hetzner AX162-R — `amplified-core` (`135.181.161.131`)

| Spec | Value |
|------|-------|
| CPU | AMD EPYC 9454P 48-Core (96 threads) |
| RAM | 252 GB |
| Disk | 1.8 TB RAID, ~170 GB used (11%) |
| OS | Ubuntu 24.04.4 LTS |

The Brain runs 24/7 on dedicated hardware, entirely decoupled from local laptops or residential internet connections.

### Production fleet (canonical — see `02_build/INFRASTRUCTURE.md` for full container inventory)

| Category | Services |
|----------|----------|
| **Database** | PostgreSQL (primary + secondary), Redis, ClickHouse, MinIO |
| **Intelligence** | Ollama (local LLMs), LiteLLM (proxy/failover), Token-proxy (Anthropic routing), SearXNG, Langfuse |
| **Orchestration** | Temporal Server, Cove API + workers (alpha/bravo/charlie/delta), Enforcer |
| **Agents** | OpenClaw Agents, Amplified Knowledge MCP |
| **Product** | Amplified Core API, Amplified Worker, Finance Engine, Marketing Engine, Kaizen Optimizer |
| **Voice** | Voice Agent (Twilio/Deepgram/Anthropic), xAI Phone Agent |
| **Legacy (running, deprecated for new work)** | FalkorDB, Qdrant |

**Rule: The Hetzner server is the ONLY place where production intelligence is generated and stored.**

---

## 3. The Dumb Terminal (The Founder's Laptop)

**Physical location:** Local MacAir M5 (`/Users/ewansair/clean-build/...`)

The laptop is intentionally downgraded to a "Dumb Terminal" (The Optic Nerve). It passes information up to the Brain but processes nothing locally.

| Function | What it does |
|----------|-------------|
| **Code Sandbox** | Safe environment where agents draft and test scripts before deployment. |
| **Archive Ingress** | Landing zone for raw markdown, client transcripts, brain dumps. |
| **Synapse** | Files dropped locally are synced via `rsync` to Hetzner, where the Brain autonomously digests them. |

**Rule: No production databases, orchestration engines, or final autonomous execution occurs on the local M5.**

---

## 4. The Agent Swarm (Who Operates the Brain)

| Agent | Platform | Role | Brain access |
|-------|----------|------|-------------|
| **Devon** (Devin) | Cloud sessions (Devin platform) | Software engineer, infrastructure, governance, scheduled ops | Full read/write via SSH + GitHub + Linear |
| **Cursor** | Local M5 / cloud sessions | Technical genius, code architect, compound engineering | **Full read/write** — drafts on M5, pushes via Git. Reads this file for architectural context. |
| **Cassian** (Claude) | claude.ai / Perplexity Computer | Strategy, research synthesis, doctrine compilation | Read via MCP + vault; write via PR proposals |
| **Antigravity** (Perplexity) | Perplexity platform | Research, competitive intelligence, web search, COO/Arbiter | Read via search + vault; write via content pipeline |
| **OpenClaw** | Self-hosted (Beast) | Note-taking, recording, coordination, weekly governance review | Read/write via local API on Beast |

### Cursor — full read/write access

Cursor has full read/write access to the Brain's architecture and codebase:

1. **Read**: This file (`00_authority/BRAIN_ARCHITECTURE.md`), the full `00_authority/` spine, `02_build/INFRASTRUCTURE.md`, and all code in the workspace.
2. **Write**: May propose changes to any file via PR. Authority files (`00_authority/*`) follow the normal review gate (`CODEOWNERS` requires Ewan). Code in `02_build/` follows standard PR workflow.
3. **Spin up sub-agents**: Cursor may use compound engineering to parallelise work across sub-agents.
4. **Brain queries**: Cursor may query the Knowledge MCP for semantic and graph lookups against the Brain's data.

---

## 5. The Workflow (Draft → Sync → Rebuild → Execute)

The protocol exists to prevent "local blindness" — agents building infrastructure on the M5 instead of the Brain.

```
1. DRAFT    Agent writes code (M5 / Devin session / cloud IDE)
2. SYNC     Code pushed to GitHub → pulled on Hetzner (Git or rsync)
3. REBUILD  Docker containers rebuilt on Hetzner to inherit new logic
4. EXECUTE  Temporal fires workflows; agents execute updated business logic
```

| Step | Who | Where |
|------|-----|-------|
| Draft | Any agent | M5 (Cursor), Devin session (Devon), claude.ai (Cassian) |
| Sync | Git push / rsync | GitHub → Hetzner |
| Rebuild | Devon (scheduled or triggered) | Hetzner: `docker compose build` |
| Execute | Temporal + Cove workers | Hetzner only |

**Rule: Execution happens on the Brain (Hetzner). Drafting can happen anywhere. The gap between Draft and Execute is Git.**

---

## 6. Data Flow (How Knowledge Enters the Brain)

```
Raw Dump → Archive (Clean Room) → Brain (Active Engine)
```

### Step 1: Raw Dump

Messy inbox. Humans, web-scrapers, and agents dump raw text, audio transcripts, and rough notes. Lands in `corpus-raw` repo or local archive ingress.

### Step 2: Archive (The Clean Room)

Automated pipeline hands raw files to an LLM for extraction. The LLM acts as a strict librarian — extracts only:

- **Recipes**: actionable patterns ("If you send this email on Tuesday, open rates go up 10%.")
- **Concepts**: named ideas ("The Strangler Fig strategy.")
- **Signals**: emerging trends ("New pattern in AI-assisted onboarding.")

Clean summaries are saved with PUDDING taxonomy labels (`WHAT.HOW.SCALE.TIME`). The Archive is the permanent historical record — never deleted.

### Step 3: The Brain (Active Engine)

Clean summaries are injected into the Brain's three layers:

- **Vector layer (pgvector)**: Embeddings for semantic search. "Find everything related to customer churn in real estate."
- **Graph layer (AGE)**: Relationships for traversal. "What recipes connect to this concept? What signals led to this recipe?"
- **Orchestration layer (Temporal)**: Triggers workflows when new data arrives. "New signal detected → run competitive analysis → generate brief."

### Graph Decay (keeping the Brain fast)

- **Recently-used tagging**: Every time an agent queries a piece of data, it is tagged as active. Data unused for 6 months decays out of the active Brain. (Original file stays safe in the Archive.)
- **Deduplication**: 50 notes saying the same thing about "How to write an invoice" are merged into one Master Rule. The 50 originals are archived.

---

## 7. Terminology (locked)

| Term | Meaning |
|------|---------|
| **The Brain** | The full intelligence engine: PostgreSQL (vector + graph + relational) + Temporal orchestration, running on Hetzner. |
| **The Beast** | The Hetzner AX162-R server itself (`amplified-core`, `135.181.161.131`). |
| **The Dumb Terminal** | Ewan's MacAir M5. Passes data up; processes nothing. |
| **The Optic Nerve** | Synonym for Dumb Terminal. |
| **pgvector** | PostgreSQL extension for vector similarity search (HNSW indexing). NOT Qdrant. NOT a separate service. |
| **Apache AGE** | PostgreSQL extension for graph queries (openCypher). NOT FalkorDB. NOT Neo4j. NOT a separate process. |
| **HNSW** | Hierarchical Navigable Small World — the vector indexing algorithm. O(log n). A mathematical algorithm, not a product. |
| **"The Russian maths"** | Ewan's name for HNSW. Malkov & Yashunin (2016). |
| **PUDDING** | Taxonomy for data labelling: `WHAT.HOW.SCALE.TIME`. 2,058 possible labels (7x7x7x6). Neutral — describes what content IS. |
| **Cove** | Workflow orchestration layer running on Temporal. |

---

## 8. Agent Rules (architectural constraints)

1. **No new work on FalkorDB or Qdrant.** All new graph work → Apache AGE. All new vector work → pgvector.
2. **No production execution on the M5.** The M5 is a drafting terminal. Execution happens on the Beast.
3. **Git is the gap.** Code moves from draft to production through Git. No rsync-only deployments for production logic.
4. **One database engine.** PostgreSQL handles relational, graph, and vector. Do not provision additional database services.
5. **Radical Attribution.** Every change to the Brain's architecture is signed and logged. This file has a changelog.

---

## Changelog

### v1 — 2026-05-14

- Initial authoritative version. Replaces Linear document "The Amplified Brain Architecture (Where the Brain Lives)" (c655776f3baa, dated 2026-05-07).
- Updated data architecture: FalkorDB → PostgreSQL + Apache AGE; Qdrant → PostgreSQL + pgvector (HNSW). Per canonical Data Architecture decision (2026-05-08).
- Added full agent swarm table with Cursor full read/write access.
- Added data flow section (Raw Dump → Archive → Brain).
- Added locked terminology table.
- Added architectural constraint rules.
- Cross-references `02_build/INFRASTRUCTURE.md` for full container inventory.

Signed-by: Devon-3386 | 2026-05-14 | devin-338635b0d3cd4a868f1cf7e7fcb8d461
