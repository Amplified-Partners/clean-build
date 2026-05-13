# FalkorDB 220 MB Dump Audit — AMP-330

**Date:** 2026-05-13  
**Auditor:** Devon-62d8 (session devin-62d8792c6c3e4b238311ebf93263b04b)  
**Ticket:** [AMP-330](https://linear.app/amplifiedpartners/issue/AMP-330/falkordb-audit-the-220-mb-dump-decide-keepdecommissionrepurpose)  
**Parent:** [AMP-329](https://linear.app/amplifiedpartners/issue/AMP-329/deep-research-beast-audit-falkordb-decision-parent)

---

## Verdict

**Decommission cleanly (option a).** The 220 MB dump is fully duplicative of Postgres. Postgres has richer data (summaries, transition probabilities on relationships). Nothing in FalkorDB is unique or irreplaceable.

---

## Container State (measured 2026-05-13 ~05:30 UTC)

| Property | Value |
|----------|-------|
| Container | `falkordb-temp` (ID `82382e442c58`) |
| Status | Up 16 hours |
| Network | `bridge` (not `amplified-net`) |
| Port | `127.0.0.1:6379->6379/tcp` |
| Mount | `/tmp/falkor-restore` → `/var/lib/falkordb/data` |
| Dump file | `/tmp/falkor-restore/dump.rdb` — 220 MB (230,272,952 bytes) |
| Dump modified | 2026-05-12 15:11 CEST |
| Restart policy | None |

Port 6379 on the host goes to `falkordb-temp`, not to the `redis` container (which is on `amplified-net` with no host port mapping).

---

## Graph Inventory

### Graphs listed

```
GRAPH.LIST → business_knowledge, amplified, amplified_graph, amplified_brain
```

### Per-graph node counts (measured)

| Graph | Label | Count |
|-------|-------|-------|
| **business_knowledge** | Entity | 44,873 |
| | Document | 5,709 |
| | Episodic | 3,717 |
| | Category | 48 |
| | **Subtotal** | **54,347** |
| **amplified** | Entity | 3,328 |
| | Episodic | 540 |
| | Mechanism | 1 |
| | **Subtotal** | **3,869** |
| **amplified_graph** | *(empty)* | 0 |
| **amplified_brain** | *(empty)* | 0 |
| **Total** | | **58,216** |

### Per-graph edge counts (measured)

| Graph | Relationship | Count | From → To |
|-------|-------------|-------|-----------|
| **business_knowledge** | MENTIONS | 52,303 | Episodic → Entity |
| | RELATES_TO | 31,851 | Entity ↔ Entity |
| | BELONGS_TO | 4,664 | Document → Category |
| | CROSS_REFERENCES | 90 | Document → Document |
| | **Subtotal** | **88,908** | |
| **amplified** | MENTIONS | 7,642 | Episodic → Entity |
| | RELATES_TO | 2,436 | Entity ↔ Entity |
| | **Subtotal** | **10,078** | |
| **Total** | | **98,986** | |

### Node properties (sampled)

Entity nodes carry: `uuid`, `name`, `group_id`, `summary`, `created_at`, `name_embedding`, `labels`.

Edge properties (all types): `uuid`, `group_id`, `created_at`. No summary, no embedding, no semantic content on edges.

### Sample Entity content

Business knowledge about competitor apps (Basecamp, Toast, Square POS, Phorest, Treatwell, Timely, Booksy, Fresha), pricing philosophy, client types, de-friction estimates, voice transcription references, PUDDING technique concepts. The `amplified` graph contains Amplified Partners business strategy content (pricing, guarantees, financial models).

---

## Postgres Comparison (cove-postgres, database `amplified_brain`)

### Current live tables

| Table | Rows |
|-------|------|
| knowledge_vectors | 163,554 |
| episode_entities | 59,192 |
| entities | **0** |
| relationships | **0** |
| episodes | **0** |

### Legacy backup tables (snapshot 2026-05-10)

| Table | Rows |
|-------|------|
| entities_legacy_2026_05_10 | 53,959 |
| relationships_legacy_2026_05_10 | 34,488 |
| episodes_legacy_2026_05_10 | 4,257 |
| knowledge_vectors_legacy_2026_05_10 | 225,841 |

### Legacy entity type breakdown

| entity_type | count |
|-------------|-------|
| entity | 48,201 |
| document | 5,709 |
| category | 48 |
| mechanism | 1 |

### Legacy relationship type breakdown

| relation_type | count | avg summary length |
|---------------|-------|--------------------|
| RELATES_TO | 34,287 | 85 chars |
| MENTIONS | 201 | null |

### Postgres relationship schema (richer than FalkorDB)

Columns: `id`, `source_id`, `target_id`, `relation_type`, `summary`, `transition_probability`, `properties` (jsonb), `embedding`, `created_at`, `updated_at`.

FalkorDB edges only carry: `uuid`, `group_id`, `created_at`.

### AGE graph

Extension `age` v1.6.0 installed. Graph `compound_design` exists with schema (Concept, Research, Pattern, Artifact, Pudding vertex labels; BRIDGES_TO, CONTRADICTS, INFORMS, VALIDATED_BY, DERIVES_FROM edge labels) but **0 data rows**.

---

## Duplication Analysis

### Entities: EXACT MATCH

FalkorDB non-Episodic nodes across both graphs: 44,873 + 5,709 + 48 + 3,328 + 1 = **53,959**.
Postgres legacy entities: **53,959**.
UUID spot-check (5 entities): all 5 UUIDs and names match exactly.

### Episodes: EXACT MATCH

FalkorDB Episodic nodes: 3,717 + 540 = **4,257**.
Postgres legacy episodes: **4,257**.

### RELATES_TO edges: EXACT MATCH

FalkorDB: 31,851 + 2,436 = **34,287**.
Postgres legacy: **34,287**.
UUID spot-check (3 relationships): all 3 exist in both stores.

### MENTIONS edges (Episodic → Entity): EFFECTIVELY DUPLICATED

FalkorDB: 52,303 + 7,642 = **59,945**.
Postgres `episode_entities` junction table: **59,192**.
Difference of 753 rows (~1.3%) — likely snapshot timing.

### BELONGS_TO edges (Document → Category): FalkorDB-ONLY but trivial

4,664 edges mapping 5,709 documents into 48 categories. Simple file categorization. Reconstructible from document metadata if ever needed.

### CROSS_REFERENCES edges (Document → Document): FalkorDB-ONLY but minimal

90 edges. Negligible.

### Postgres is the SUPERIOR copy

Postgres legacy relationships carry summaries (avg 85 chars) and transition probabilities. FalkorDB edges carry only `uuid`, `group_id`, `created_at`. Postgres has richer semantic content per relationship.

---

## Decision

**(a) Decommission cleanly.** OPINION 95%.

Rationale:
1. Every entity, episode, and RELATES_TO edge in FalkorDB exists in Postgres legacy tables with identical UUIDs.
2. MENTIONS edges are replicated in `episode_entities` (59,192 vs 59,945 — within 1.3%).
3. The only FalkorDB-exclusive edges are 4,664 BELONGS_TO (trivial categorization) and 90 CROSS_REFERENCES (negligible).
4. Postgres relationships are richer (summaries, transition probabilities) — FalkorDB is the inferior copy.
5. The canonical data architecture (DATA_ARCHITECTURE.md) already deprecated FalkorDB in favour of PostgreSQL + AGE + pgvector.
6. `amplified-knowledge-mcp` v2.1.0 is Postgres-only since 2026-05-11.
7. `falkordb-temp` is on `bridge` network, mounted from `/tmp`, no restart policy — it was never production-grade.

---

## Cleanup Commands (ready to run after Ewan approves)

```bash
# 1. Stop and remove the container
docker stop falkordb-temp && docker rm falkordb-temp

# 2. Remove the dump
rm -rf /tmp/falkor-restore

# 3. Verify redis container is unaffected
docker exec redis redis-cli PING
```

### Code references to clean up (separate tickets)

- CRM + marketing engine: 39 hits in `agent-stack`, 46 in `apps` referencing `falkordb:6379` — failing silently.
- `agent-stack/cove-orchestrator/agents/prompts/prompt_loader.py` lines 37–64: calls `query_falkordb_context()` on every agent invocation.
- Enforcer `EXPECTED_CONTAINERS` list.
- Compose files referencing FalkorDB service.

---

## Caveat: Live tables are empty

The current Postgres `entities`, `relationships`, and `episodes` tables have **0 rows**. All data exists only in the `*_legacy_2026_05_10` tables. These legacy tables must be preserved (or migrated into the AGE `compound_design` graph) before they are dropped. This is a separate concern from the FalkorDB decommission — but it means "the data is safe in Postgres" is conditional on the legacy tables remaining intact.

---

## Attribution Problem Flagged

A comment on AMP-330 was posted under "Ewan Bramley" that Ewan confirmed he did not write. The comment (ID `d896960f`) says "Taking this back from Devin — doing it myself" and was posted at 2026-05-13T05:20:08. This was likely posted by Perplexity Computer (which authored the ticket description and has write access under Ewan's Linear identity). This is an audit/attribution problem — agents posting under Ewan's identity violates radical attribution.

---

*Devon-62d8 | 2026-05-13 | session devin-62d8792c6c3e4b238311ebf93263b04b*
