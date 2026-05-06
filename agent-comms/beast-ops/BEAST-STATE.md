# Beast — Current State

*Last verified: 2026-05-06 18:15 UTC by Devon-6164 (live SSH audit).*
*Update this file when you change anything on the Beast.*

---

## Hardware

```
IP:       135.181.161.131
SSH:      ssh -i ~/.ssh/beastkey root@135.181.161.131
Hardware: Hetzner AX162-R · AMD EPYC 9454P · 96 threads · 251GB RAM
Disk:     1.8TB (1.4TB free)
OS:       Ubuntu 24.04 LTS
Uptime:   9 days at time of writing
```

---

## Critical: Services Are in Docker

**All services run inside Docker containers on the `amplified-net` bridge network.**

This means:

- `curl http://localhost:6333` → **silence** (Qdrant is not on the host)
- `redis-cli -p 6379 ping` → **fails** (FalkorDB is not on the host)
- `psql -h localhost` → **fails** (Postgres is not on the host)

**How to query services correctly:**

```bash
# FalkorDB (graph DB)
docker exec falkordb redis-cli GRAPH.LIST
docker exec falkordb redis-cli GRAPH.QUERY business_knowledge \
  'MATCH (n) RETURN labels(n) AS type, count(n) AS cnt ORDER BY cnt DESC'

# Qdrant (vector DB) — get container IP first
QDRANT_IP=$(docker inspect qdrant --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
curl -s http://$QDRANT_IP:6333/collections | python3 -m json.tool

# Postgres
docker exec postgres psql -U amplified -d amplified_main -c '\l'

# Redis
docker exec redis redis-cli ping
```

**After port bindings are applied** (see `02_build/beast/falkordb/docker-compose.beast.snapshot.yml`), these shortcuts also work from the host:

```bash
# FalkorDB (on port 6380 — NOT 6379, which is Redis)
redis-cli -p 6380 GRAPH.LIST
redis-cli -p 6380 GRAPH.QUERY business_knowledge 'MATCH (n) RETURN labels(n), count(n)'

# Qdrant
curl -s http://localhost:6333/collections | python3 -m json.tool

# Postgres
psql -h localhost -U amplified -d amplified_main -c '\l'

# Redis
redis-cli -p 6379 ping
```

To check whether port bindings are active: `docker inspect <container> --format '{{.HostConfig.PortBindings}}'` — if it returns `map[]`, there are no host bindings and you must use `docker exec`.

---

## What's Running (42 containers)

### Data Layer

| Container | Internal Port | Docker Network IP | What |
|-----------|--------------|-------------------|------|
| `falkordb` | 6379 | 172.18.0.22 | Graph DB — FalkorDB |
| `qdrant` | 6333/6334 | 172.18.0.31 | Vector DB |
| `postgres` | 5432 | 172.18.0.10 | PostgreSQL (6 databases) |
| `redis` | 6379 | 172.18.0.27 | Cache, PII token TTL |
| `minio` | 9000 | — | Object storage |
| `clickhouse` | — | — | Analytics |

**Note:** Docker IPs can change on container restart. Always use `docker inspect` to get the current IP, or use `docker exec`.

### AI Layer

| Container | Port | What |
|-----------|------|------|
| `litellm` | 4000 | Model router (Claude, GPT-4.1, Llama, Qwen3) |
| `ollama` | 11434 | Local LLM inference (zero API cost) |
| `openclaw-agents` | 8100 | LangGraph agent runtime |
| `amplified-knowledge-mcp` | — | MCP server for FalkorDB + Qdrant (read-only) |
| `langfuse` | — | LLM observability |
| `searxng` | 8080 | Private web search |

### Application Layer

| Container | What |
|-----------|------|
| `amplified-core` | Core AP service |
| `amplified-marketing-engine` | Content pipeline |
| `enforcer` | Security and content moderation |
| `nexus-dashboard` | Dashboard |
| `kaizen-optimizer` | Continuous improvement |
| `cove-temporal` + `cove-worker-*` (6) | Temporal workflow engine |
| `entity_alpha`, `entity_charlie`, `entity_kimmy` | Sovereign fleet agents |
| `traefik` | HTTPS proxy (`*.beast.amplifiedpartners.ai`) |
| `portainer` | Docker UI |
| `watchtower` | Auto-updates |

---

## What's in the Databases

### FalkorDB — 4 graphs

| Graph | Nodes | Edges | Status |
|-------|-------|-------|--------|
| `business_knowledge` | 53,251 (43,892 Entity, 5,699 Document, 3,612 Episodic, 48 Category) | 86,718 (51,108 MENTIONS, 30,856 RELATES_TO, 4,664 BELONGS_TO, 90 CROSS_REFERENCES) | **Active — Graphiti enriching** |
| `amplified` | 3,869 (3,328 Entity, 540 Episodic, 1 Mechanism) | 10,078 (7,642 MENTIONS, 2,436 RELATES_TO) | Stable |
| `amplified_graph` | Empty | — | Created, not populated |
| `amplified_brain` | Empty | — | Created, not populated |

### Qdrant — 5 collections

| Collection | Points | Dimensions | Status |
|------------|--------|------------|--------|
| `amplified_knowledge` | **57,434** | 384 | Green — main vault embeddings |
| `llm_cache` | 2 | 384 | Green |
| `content_embeddings` | 0 | 1536 | Green — empty, for future use |
| `person_profiles` | 0 | 768 | Green — empty, for future use |
| `knowledge_base` | 0 | 1536 | Green — empty, for future use |

### Postgres — 6 databases

`amplified_main`, `amplified_crm`, `amplified_machine`, `langfuse`, `litellm`, `marketing`.

### Vault (disk) — 26,494 files

Location: `/opt/amplified/vault/`
77 categories. Largest: `store_b_clean` (3.9GB), monologue transcripts (11MB), voice captures (9.4MB).

---

## Key Paths

```
/opt/amplified/                     # Root
/opt/amplified/docker-compose.yml   # Main compose (FalkorDB, Postgres, Redis, Qdrant, Portainer, Watchtower)
/opt/amplified/vault/               # 26,494 markdown files, 77 categories
/opt/amplified/apps/                # Application code (CRM, openclaw-agents, litellm, etc.)
/opt/amplified/apds/                # APDS pipeline
/opt/amplified/secrets/             # Secret files (pg_password.txt, etc.)
/opt/amplified/ACCESS_RULES.md      # Agent access rules
/opt/amplified/{devon,clawd,cassian,antigravity,hermes}/  # Agent workspaces
/opt/amplified/Entity_{Alpha,Charlie,Kimmy}/               # Sovereign fleet workspaces
```

---

## Known Issues (as of 2026-05-06)

- **Traefik :8080 dashboard unreachable** (AMP-140)
- **Tailscale stuck in Created state** since 2026-05-02 (AMP-136)
- **LLM providers degraded:** OpenAI/Moonshot 401, Anthropic billing exhausted (AMP-142)
- **amplified-crm-dev** container in restart loop (CRM codebase issues — missing modules, eager imports)
- **Graphiti** running but limited throughput — processing 8,979 files, 2,659 done

---

## Quick Health Check

```bash
ssh -i ~/.ssh/beastkey root@135.181.161.131

# Are containers up?
docker ps --format 'table {{.Names}}\t{{.Status}}' | sort

# FalkorDB alive?
docker exec falkordb redis-cli ping

# FalkorDB node count?
docker exec falkordb redis-cli GRAPH.QUERY business_knowledge \
  'MATCH (n) RETURN labels(n) AS type, count(n) AS cnt ORDER BY cnt DESC'

# Qdrant alive?
QDRANT_IP=$(docker inspect qdrant --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
curl -s http://$QDRANT_IP:6333/collections | python3 -m json.tool

# Postgres alive?
docker exec postgres psql -U amplified -d amplified_main -c 'SELECT 1'

# Redis alive?
docker exec redis redis-cli ping
```

---

*Devon-6164 | 2026-05-06 | session devin-6164c4ee90b94eea8d66b864d041e2ef*
