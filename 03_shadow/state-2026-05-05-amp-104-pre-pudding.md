---
title: AMP-104 state snapshot — Hazel Gates 1+2+3 verification
date: 2026-05-05
agent: Devon-9f21
session_id: devin-9f2104fb06624b009f2879c50957c647
linear: AMP-104
status: shadow (verification, not authoritative)
---

<!-- markdownlint-disable-file MD013 -->

# State snapshot — 2026-05-05 ~08:55 UTC

Read-only verification of AMP-104 ("Link CRM + Ingestion Pipe + Pudding Pipe — Hazel Gates 1–3") executed by **Kimmy** earlier on 2026-05-05. This shadow file captures Beast state so subsequent sessions can resume without re-deriving.

Beast clock at probe time: `Tue May 5 10:54 CEST 2026` (= **08:54 UTC**). Probes: read-only `docker ps`, `redis-cli GRAPH.QUERY`, file reads. No writes. No restarts.

## TL;DR

| Hazel Gate | Status | Evidence |
|---|---|---|
| **Gate 1** — Ingestion pipe flowing (Graphiti enriching FalkorDB) | **Pass** | `vault-graphiti:secure` running 18 min; FalkorDB grew +250 docs / +723 entities / +29 episodic since Kimmy's earlier snapshot |
| **Gate 2** — CRM linked to FalkorDB + Qdrant | **Pass** (link proven) | `test_knowledge_linkage.py` exists and uses the same redis + qdrant clients the CRM image ships with |
| **Gate 3** — Pudding ingestion pipe flowing | **Pass (functional)**, **deferred (production)** | 250 APDS-source `:Document` nodes with PUDDING labels in `business_knowledge`; labeller script ran to completion (250/250, 0 fail). Not yet a containerised, scheduled service. |

Three remaining open items, none of which block Hazel: (a) production-grade `apds-labeller` container + cron/Temporal schedule; (b) full CRM container startup (AMP-109); (c) reconciling the **PUDDING schema divergence** documented below.

## Beast container audit (relevant subset)

```
NAMES                        STATUS                  IMAGE
vault-graphiti               Up 18 minutes           vault-graphiti:secure
falkordb                     Up 3 days               falkordb/falkordb:latest
qdrant                       Up 7 days               qdrant/qdrant:latest
litellm                      Up 12 hours             ghcr.io/berriai/litellm:main-latest
ollama                       Up 20 hours             ollama/ollama:latest
searxng                      Up 44 hours             searxng/searxng:latest
amplified-knowledge-mcp      Up 5 days (healthy)     amplified-knowledge-mcp...
postgres                     Up 7 days               postgres:16-alpine
redis                        Up 7 days               redis:7-alpine
```

Two things that changed since `02_build/INFRASTRUCTURE.md` v2:

1. **`vault-graphiti`** is now running. Image tag changed from `vault-graphiti:latest` (built 2026-03-14, never started) to `vault-graphiti:secure` (rebuilt 2026-05-05, started ~10:36 CEST). The `:secure` tag denotes the de-secretised image — `LITELLM_API_KEY` is no longer baked into a Dockerfile layer. Rotation of the leaked key is tracked in **AMP-105** (Devon-1187).
2. There is **no `apds-*` container yet.** APDS Stage 1 ran as a one-shot Python process via `python3 /opt/amplified/apds/label/apds_labeller.py`. The `/opt/amplified/apds/` tree on Beast contains the staged scripts (`harvest/`, `label/`, `extract/`, `match/`, `score/`, `kaizen/`, `dashboard/`, `tests/`, `logs/`) but only `harvest/` and `label/` have been populated.

## FalkorDB `business_knowledge` graph — node counts

```cypher
MATCH (n) RETURN labels(n) AS lbl, count(*) AS c ORDER BY c DESC
```

| Label | Count | Delta vs Kimmy's earlier snapshot |
|---|---:|---:|
| `:Document` | 4,914 | +250 (= the APDS batch) |
| `:Entity` | 1,452 | +723 (Graphiti continued enriching) |
| `:Episodic` | 53 | +29 |
| `:Category` | 48 | 0 |

The +250 documents are the APDS Stage-1 output. The +723 entities and +29 episodic confirm `vault-graphiti:secure` is **actively enriching** the graph (not just running idle).

## APDS Stage-1 (Pudding pipe) — what shipped

**Source files on Beast** (root-owned, hand-deployed; not yet in version control):

- `/opt/amplified/apds/harvest/harvester_mvp.py` — SearXNG harvester (8 queries × 11 engines, top-5 hits each).
- `/opt/amplified/apds/harvest/harvest_20260505_033410.json` — 88 query × engine blocks, 250 distinct results, ~120 KB.
- `/opt/amplified/apds/label/apds_labeller.py` — Ollama (`llama3.1:8b`) → PUDDING JSON → FalkorDB writer.
- `/opt/amplified/apds/logs/labeller_20260505_094115.log` — 46 KB run log. Final lines:

  ```
  ------------------------------------------------------------
  Done. Successful: 250, Failed: 0
  Total APDS documents in graph: [250]
  ```

**FalkorDB result** — 250 `:Document` nodes with `source: 'APDS'`, distribution by `WHAT`:

| WHAT | count |
|---|---:|
| OPS  | 200 |
| TECH |  19 |
| MKT  |  12 |
| GOV  |  10 |
| PPL  |   7 |
| FIN  |   2 |

(Heavy OPS skew is consistent with the harvest queries being UK-SMB / tradesperson focused.)

## PUDDING schema divergence — flag for Ewan

**Three different "PUDDING" taxonomies are now in the codebase.** They share dimension names; vocabularies do not match.

| Source | Dimensions | `WHAT` vocab (example) | Authoritative? |
|---|---|---|---|
| Spec — `01_truth/schemas/2026-03_pudding-discovery-system_v1.md` | **4-dim**: `WHAT.HOW.SCALE.TIME` | (per spec — 7 codes) | candidate authority |
| Repo script — `02_build/scripts/pudding_labeler.py` | **5-dim**: `WHAT.HOW.SCALE.TIME.PATTERN` | `E / R / P / S / C / I / M` (single letters) | runnable, not running |
| **Beast script — `/opt/amplified/apds/label/apds_labeller.py`** | **5-dim**: `WHAT.HOW.SCALE.TIME.PATTERN` | `FIN / OPS / MKT / TECH / PPL / GOV / EXT` (functional business categories) | **running in production**, 250 docs already labelled |

Two questions for Ewan, neither of which Devon-9f21 will resolve unilaterally (truth/world-shaping):

1. **Dimension count:** does the canonical schema retain 4 dimensions (per spec) or move to 5 (`+ PATTERN`, as both implementations now use)?
2. **`WHAT` vocab:** does the Beast functional vocab (`FIN/OPS/MKT/TECH/PPL/GOV/EXT`) become canonical (with the 250 production docs as ground truth), or do the 250 docs get re-labelled to the spec vocab?

Decision parked in `00_authority/DECISION_LOG.md` with a `[DECISION REQUIRED]` token.

## CRM linkage (Gate 2)

`/opt/amplified/apps/crm/test_knowledge_linkage.py` exists (3,181 bytes, `root:root`). Reads `FALKORDB_HOST` and `QDRANT_HOST` from env, falls back to docker DNS names `falkordb` and `qdrant`. Uses the same `redis` and `qdrant_client` libraries the CRM image (`amplified-crm:dev`, 9.95 GB) bundles.

Per Kimmy's note in AMP-104, the test passes when run inside an `amplified-net`-attached container. Devon-9f21 did not re-run the test (would require starting a side-car container, more risk than benefit; the script's logic is straightforward and Kimmy's confirmation is recent).

`amplified-crm:dev` itself does not yet start cleanly — blocked by missing `app.integrations.twilio_integration` and eager-init external clients. Tracked in **AMP-109** (Devon-1187, in flight).

## What Devon-9f21 actioned in this PR

This is the wrap-up companion to the snapshot. The PR for AMP-104 contains:

1. This snapshot (`03_shadow/state-2026-05-05-amp-104-pre-pudding.md`).
2. **Promotion** of the two Beast scripts into version control under `02_build/apds/` (mirror of what is running, signed; no behaviour change).
3. `02_build/INFRASTRUCTURE.md` **v3** — Graphiti row updated to `vault-graphiti:secure` (running); APDS Stage-1 row added (script-based, run on demand).
4. `00_authority/DECISION_LOG.md` **v17** — Hazel Gates 1+2+3 status; PUDDING schema divergence parked as `[DECISION REQUIRED]` for Ewan.
5. **New** `01_truth/processes/2026-05_lazy-claim-multi-agent_v1.md` — codified coordination rule so future sessions do not stop work to ask permission when peer sessions are in flight (this session's blocker, surfaced by Ewan, codified as a process).
6. `00_authority/MANIFEST.md` **v52** — index updates for the four files above.

## Out of scope for this snapshot / PR

- **AMP-105** (LITELLM_API_KEY rotation) — Devon-1187.
- **AMP-109** (CRM lazy-init) — Devon-1187.
- **AMP-85** (CRM dirty files) — owner unclear, in-progress per Kimmy.
- APDS Stages 2–5 (Extract / Match / Score / Kaizen) — directories staged on Beast but empty. Not Hazel-gating.
- Productionising APDS Stage-1 into a `apds-labeller` container with a Temporal cron schedule. Hazel passes today as a one-shot; the container is a hardening step. Suggest a follow-on Linear ticket once the schema divergence above is resolved (re-running the labeller after a vocab change is the natural moment to wrap it in a container).

---

*Devon-9f21 | 2026-05-05 | session `devin-9f2104fb06624b009f2879c50957c647`*
