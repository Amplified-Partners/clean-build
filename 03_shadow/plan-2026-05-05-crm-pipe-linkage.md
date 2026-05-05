# Plan: Link CRM + Ingestion Pipe + Pudding Pipe

**Date:** 2026-05-05  
**Agent:** Kimmy  
**Job:** Link up the CRM, the ingestion pipe, and the new pudding ingestion pipe (Ewan's Hazel gate conditions)  
**Compound Engineering Loop:** Plan → Work → Review → Compound

---

## 1. PLAN (40%)

### What is the job?
Ewan wants three things linked before Hazel runs:
1. CRM linked to the knowledge graph (FalkorDB + Qdrant)
2. Ingestion pipe flowing (vault → graph → vectors)
3. New pudding ingestion pipe flowing (APDS harvest → label → match)

### What do I know?
- **CRM repo** (`Amplified-Partners/crm`): Clean, no hardcoded secrets, 153 FastAPI endpoints, `secrets.py` with 1Password integration
- **Beast containers running:** FalkorDB, Qdrant, LiteLLM, Ollama, PostgreSQL, Redis, SearXNG, Enforcer, Kaizen, Marketing Engine
- **Ingestion pipe:** `ingest_vault.py` exists and runs. `graphiti_ingest.py` exists as Docker image (`vault-graphiti:latest`) but **NO CONTAINER RUNNING**
- **FalkorDB:** `business_knowledge` graph with 4,664 docs, 255 entities, 48 categories, 6 episodic, **0 topics**
- **Qdrant:** `amplified_knowledge` collection, 57,434 vectors, 384-dim
- **PUDDING labeller:** Exists at `/opt/amplified/pudding-testing/`, tested and working
- **APDS harvester:** MVP tested, produced 88 entries from SearXNG

### What do I NOT know?
- Does Beast have a PostgreSQL DB schema ready for CRM?
- Is the Graphiti image actually functional? (Built Mar 14, never started)
- How does CRM connect to FalkorDB? (Direct Cypher queries? Via MCP server?)
- What's the status of Graphiti enrichment? (Ewan: "I don't think we even have a Graphiti database")

### What could go wrong?
- **Security:** Graphiti Dockerfile has hardcoded `LITELLM_API_KEY=sk-MoJPRBEtIJRJM7J7ZCw6fQ` — plaintext secret in container image
- **Architecture:** CRM should be Edge/Cloud per North Star. Beast deployment is dev/staging only.
- **Scope creep:** This could turn into "build the entire APDS" if I'm not careful. Ewan said "link up," not "build from scratch."

### What is the smallest executable step?
**Step 1:** Verify what actually exists on Beast (don't assume). Check if Graphiti ever ran, check if CRM DB exists.
**Step 2:** Fix the security issue in Graphiti Dockerfile (remove hardcoded secret).
**Step 3:** Start Graphiti container and see if it works.
**Step 4:** Write CRM docker-compose for Beast dev/staging.
**Step 5:** Wire CRM to FalkorDB/Qdrant (query layer, not full deployment).

---

## 2. WORK (Execution Steps)

| Step | Task | Time | Risk |
|------|------|------|------|
| 1 | Verify Beast state: Graphiti DB, CRM DB, FalkorDB topics | 5 min | Low |
| 2 | Fix Graphiti Dockerfile (remove hardcoded LITELLM_API_KEY) | 10 min | Medium — rebuild image |
| 3 | Start Graphiti container, check logs | 5 min | Medium — may fail |
| 4 | Fix CRM dirty files (already in progress) | 5 min | Low |
| 5 | Write CRM docker-compose.yml for Beast | 20 min | Medium |
| 6 | Wire CRM query layer to FalkorDB + Qdrant | 30 min | Medium |

---

## 3. REVIEW (Done Criteria)

- [ ] Graphiti container is running and enriching vault docs
- [ ] FalkorDB has >0 Topic nodes (proof Graphiti is working)
- [ ] CRM docker-compose exists and can be started on Beast
- [ ] CRM can query FalkorDB for knowledge graph data
- [ ] CRM can query Qdrant for semantic search
- [ ] No secrets exposed in any new files
- [ ] Linear tickets updated

---

## 4. COMPOUND (Learning Capture)

- Document the exact connection pattern CRM → FalkorDB → Qdrant
- If Graphiti image is broken, document why and the fix
- Update Portable Spine with Beast database connection details

---

**Approved by:** Ewan (verbal, 2026-05-05)  
**Next review point:** After Step 3 (Graphiti container start)
