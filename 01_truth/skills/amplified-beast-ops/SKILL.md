# amplified-beast-ops — Beast Server Operations

**Version:** 2.0
**Last verified:** 2026-05-08 21:35 UTC (live SSH audit by Devon-d37b)
**Replaces:** amplified-beast-ops v1 (Perplexity custom skill, pre-migration)
**Ticket:** AMP-192

---

## 1. Hardware

```
Name:     The Beast
IP:       135.181.161.131
SSH:      ssh -i ~/.ssh/beastkey root@135.181.161.131
Hardware: Hetzner AX162-R · AMD EPYC 9454P · 96 threads · 251 GB RAM
Disk:     1.8 TB (1.4 TB free)
OS:       Ubuntu 24.04 LTS
Network:  amplified-net Docker bridge
```

---

## 2. Amplified Brain — Postgres + pgvector + Four-Russian Stack

The Brain is **PostgreSQL with pgvector**, running in the existing `cove-postgres` container. It replaced FalkorDB (graph) and Qdrant (vector) as of 2026-05-07 (AMP-187).

### MCP Endpoints

| Endpoint | Port | Container | Access |
|----------|------|-----------|--------|
| `http://135.181.161.131:8090/mcp` | 8090 | `brain-mcp-readonly` | All agents (read-only) |
| `http://135.181.161.131:8091/mcp` | 8091 | `brain-mcp-writer` | Devon only (read + write) |

Server name: `amplified-brain-mcp` v1.0.0
Protocol: MCP (JSON-RPC 2.0 over HTTP POST), SSE transport also available at `/sse`.
Health check: `GET /health` → `{"status": "ok", "database": "amplified_brain", "writes": false}`.

### Database Schema (amplified_brain)

| Table | Size | Purpose | Replaces |
|-------|------|---------|----------|
| `knowledge_vectors` | 158 MB | Vault embeddings (384-dim, HNSW index) | Qdrant `amplified_knowledge` (57,434 vectors) |
| `entities` | 18 MB | Entity nodes (HNSW + GIN indexes) | FalkorDB entity nodes (53,959) |
| `relationships` | 28 MB | Entity edges (HNSW index) | FalkorDB edges (34,488) |
| `episodes` | 16 MB | Episodic events | FalkorDB episodic nodes (4,257) |
| `episode_entities` | 3.5 MB | Episode ↔ entity junction (59,192 links) | FalkorDB episode edges |
| `audit_log` | 8 KB | Change tracking | New |
| `pudding_labels` | 8 KB | PUDDING taxonomy labels | New |

### MCP Tools (Read)

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables with row counts |
| `describe_table` | Show columns, types, constraints for a table |
| `search_knowledge` | Text search across knowledge_vectors |
| `get_entity` | Look up entity by name (fuzzy match) + relationships |
| `query_entities` | List entities, filter by type |
| `query_relationships` | Query relationships between entities |
| `get_episodes` | List episodes with optional text search |
| `run_query` | Run arbitrary SELECT query |

### MCP Tools (Write — writer endpoint only)

| Tool | Description |
|------|-------------|
| `insert_knowledge` | Insert knowledge vector with content + metadata |
| `insert_entity` | Insert or update entity node |
| `insert_relationship` | Create relationship between entities |
| `run_write_query` | Run arbitrary INSERT/UPDATE/DELETE |

### Four-Russian Stack

The Brain's mathematical foundations are named after four Soviet/Russian mathematicians whose work underpins the platform's analytical capabilities:

| Mathematician | Year | Mathematics | Platform Application |
|---------------|------|-------------|---------------------|
| **Kantorovich** | 1941 | Optimal transport (wartime scarcity) | Knowledge graph connections — decides which documents connect to which institutional fixes |
| **Kolmogorov** | 1933 | Probability theory | Danger spiral detection — bacterial quorum sensing pattern applied to business health |
| **Markov** | — | Markov chains (epidemiology) | Business health prediction — 24-month early warning from cash flow, quorum decisions, operational metrics |
| **Pontryagin** | — | Optimal control theory | Optimization patterns across platform systems |

**Where each applies:**

- **Kantorovich** → Knowledge Vault, Swanson corpus, Advocate knowledge base
- **Kolmogorov** → The Pulse RISK rubric, death spiral detection in Engineering Spec
- **Markov** → Business health scoring, epidemiological pattern matching
- **Pontryagin** → Cross-system optimization, constraint resolution

Sources: `01_truth/schemas/architecture/2026-03_bible-human_v2.md` (Part 8A), `01_truth/schemas/2026-03_pudding-engine-deep-research_v1.md`.

---

## 3. Legacy — FalkorDB (retained as plumbing only)

**Container:** `falkordb-temp` (renamed from `falkordb` post-migration)
**Status:** Running but NOT the Brain. Retained for migration reference only.
**Classification:** MIGRATION_SOURCE (see `02_build/beast-control-mcp/src/beast_control_mcp/tools/classification.py`)

Previously held:
- `business_knowledge` graph: 53,251 nodes, 86,718 edges
- `amplified` graph: 3,869 nodes, 10,078 edges
- `amplified_graph`, `amplified_brain`: empty graphs

All data migrated to Postgres `amplified_brain` database (AMP-187, 2026-05-07).

---

## 4. Legacy — Qdrant (retained as plumbing only)

**Container:** `qdrant-temp` (renamed from `qdrant` post-migration)
**Status:** Running but NOT the Brain. Retained for migration reference only.
**Classification:** MIGRATION_SOURCE

Previously held:
- `amplified_knowledge`: 57,434 points (384-dim) — migrated to `knowledge_vectors`
- `llm_cache`: 2 points
- `content_embeddings`, `person_profiles`, `knowledge_base`: empty collections

All data migrated to Postgres `amplified_brain` database (AMP-187, 2026-05-07).

---

## 5. Container Roster

*Live from `docker ps` on Beast, 2026-05-08 21:35 UTC. 37 running, 4 created, 1 exited.*

### Brain (NEW)

| Container | Image | Status |
|-----------|-------|--------|
| `brain-mcp-readonly` | amplified-brain-mcp:latest | Up 22 hours |
| `brain-mcp-writer` | amplified-brain-mcp:latest | Up 22 hours |
| `vigorous_pascal` | ghcr.io/pgedge/postgres-mcp:latest | Up 25 hours |

### Data Layer

| Container | Image | Status |
|-----------|-------|--------|
| `cove-postgres` | timescale/timescaledb-ha:pg15-latest | Up 11 days |
| `clickhouse` | clickhouse/clickhouse-server:latest | Up 33 hours |
| `minio` | minio/minio:latest | Up 11 days |
| `falkordb-temp` | falkordb/falkordb:latest | Up 9 hours |
| `qdrant-temp` | qdrant/qdrant:latest | Up 25 hours |

### AI Layer

| Container | Image | Status |
|-----------|-------|--------|
| `litellm` | ghcr.io/berriai/litellm:main-latest | Up 35 hours |
| `ollama` | ollama/ollama:latest | Up 9 hours |
| `openclaw-agents` | openclaw-agents-openclaw-agents | Up 2 days |
| `amplified-knowledge-mcp` | amplified-knowledge-mcp (healthy) | Up 9 days |
| `plumb-knowledge-http` | amplified-knowledge-mcp (healthy) | Up 3 days |
| `langfuse` | langfuse/langfuse:latest | Up (restarting) |
| `searxng` | searxng/searxng:latest | Up 9 hours |

### Application Layer

| Container | Image | Status |
|-----------|-------|--------|
| `amplified-core` | amplified-machine-amplified-core (healthy) | Up 11 days |
| `amplified-crm` | crm-crm (unhealthy) | Up 36 hours |
| `amplified-crm-dev` | amplified-crm:dev | Up 37 hours |
| `amplified-marketing-engine` | marketing-marketing-engine | Up 2 days |
| `enforcer` | enforcer-enforcer (unhealthy) | Up 3 days |
| `kaizen-optimizer` | kaizen-kaizen (healthy) | Up 3 days |
| `nexus-dashboard` | nexus-dashboard-dashboard | Up 3 days |
| `mission-control` | mission-control-mission-control | Up 4 days |
| `amplified-code-server` | lscr.io/linuxserver/code-server:latest | Up 33 hours |

### Sovereign Fleet

| Container | Image | Status |
|-----------|-------|--------|
| `entity_alpha` | sovereign-fleet-entity_alpha:latest (healthy) | Up 2 days |
| `entity_charlie` | sovereign-fleet-entity_charlie:latest (healthy) | Up 2 days |
| `entity_kimmy` | sovereign-fleet-entity_kimmy:latest (healthy) | Up 2 days |

### Orchestration

| Container | Image | Status |
|-----------|-------|--------|
| `cove-api` | cove-api:latest (healthy) | Up 5 days |
| `cove-temporal` | temporalio/auto-setup:latest | Up 11 days |
| `cove-temporal-ui` | temporalio/ui:latest | Up 4 days |
| `cove-worker` | docker-temporal-worker:latest | Up 33 hours |
| `cove-translator` | (custom) | Up 11 days |
| `cool_jennings` | temporalio/admin-tools:1.22 | Up 2 days |

### Infrastructure

| Container | Image | Status |
|-----------|-------|--------|
| `traefik` | traefik:latest | Up 2 days |
| `token-proxy` | amplified/token-proxy:latest (healthy) | Up 4 days |
| `watchtower` | containrrr/watchtower (healthy) | Up 11 days |
| `tailscale` | tailscale/tailscale:latest | Up (restarting) |

### Stopped / Created

| Container | Status |
|-----------|--------|
| `vault-graphiti` | Exited (137) 2 days ago |
| `docker-litellm-1` | Created |
| `docker-nightscout-1` | Created |
| `docker-temporal-1` | Created |
| `docker-temporal-ui-1` | Created |

---

## 6. Key Paths

```
/opt/amplified/                       # Root
/opt/amplified/docker-compose.yml     # Main compose
/opt/amplified/brain-mcp/             # Brain MCP server source
/opt/amplified/brain-mcp-tokens.env   # Brain MCP credentials
/opt/amplified/vault/                 # 26,494 markdown files, 77 categories
/opt/amplified/apps/                  # Application code
/opt/amplified/compose/               # Additional compose files
/opt/amplified/secrets/               # Secret files
/opt/amplified/ACCESS_RULES.md        # Agent access rules
/opt/amplified/BEAST-STATE.md         # State file (update after changes)
/opt/amplified/{devon,clawd,cassian,antigravity,hermes}/  # Agent workspaces
/opt/amplified/Entity_{Alpha,Charlie,Kimmy}/               # Sovereign fleet
```

---

## 7. Quick Health Check

```bash
ssh -i ~/.ssh/beastkey root@135.181.161.131

# Brain MCP healthy?
curl -s http://localhost:8090/health | python3 -m json.tool

# Brain MCP — list tables and row counts
curl -s -X POST http://localhost:8090/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_tables","arguments":{}}}'

# Postgres alive?
docker exec cove-postgres psql -U postgres -d amplified_brain -c 'SELECT count(*) FROM knowledge_vectors'

# Containers up?
docker ps --format 'table {{.Names}}\t{{.Status}}' | sort

# Legacy FalkorDB (plumbing check only)
docker exec falkordb-temp redis-cli ping

# Legacy Qdrant (plumbing check only)
docker exec qdrant-temp wget -qO- http://localhost:6333/collections | python3 -m json.tool
```

---

## 8. Migration Reference

The Brain migration (AMP-187) is documented in `clean-build/02_build/brain-migration/`:
- `migrate_qdrant.py` — 57,434 vectors from Qdrant → `knowledge_vectors`
- `migrate_falkordb.py` — 53,959 entities, 4,257 episodes, 34,488 relationships → Postgres
- `brain_mcp_server.py` — MCP server source (FastAPI + asyncpg)
- `Dockerfile` — Container build

The architectural rationale for the Four-Russian Stack is documented in:
- `01_truth/schemas/architecture/2026-03_bible-human_v2.md` (Part 8A: Soviet maths foundations)
- `01_truth/schemas/architecture/2026-03_business-brain-framework_v1.md` (six-layer Brain stack, pgvector+AGE convergence)
- `01_truth/schemas/2026-03_pudding-engine-deep-research_v1.md` (Kolmogorov, Kantorovich, Pontryagin attribution)

---

*Devon-d37b | 2026-05-08 | AMP-192 — Rewrite amplified-beast-ops skill*
*Session: devin-d37b09d78b38487aaa6e0edabbc8ac2b*
