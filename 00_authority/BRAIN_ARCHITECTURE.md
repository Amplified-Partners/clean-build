---
title: The Amplified Brain — Architecture, Estate, and Operating Map
date: 2026-05-14
version: 2
status: authoritative now
refresh: This document MUST be refreshed every 24–48 hours by a scheduled Devon session.
supersedes: Linear doc "The Amplified Brain Architecture (Where the Brain Lives)" (c655776f3baa)
signed-by:
  - Devon-3386 | 2026-05-14 | devin-338635b0d3cd4a868f1cf7e7fcb8d461
---

<!-- markdownlint-disable-file MD013 -->

# The Amplified Brain

> **Bob decides with a Business Brain behind him.**
>
> AI is everywhere, but not in the wrong seat. The decision stays with the owner. The guessing does not.

This document is the canonical map of what the Brain is, where it lives, how it operates, and how every agent interacts with it. It is designed to be refreshed continuously — every 24–48 hours — so that any agent reading it sees the current state of the estate, not a stale snapshot.

**Cursor access: full read/write.** Cursor may read this file for architectural context and propose edits to keep it current. Changes follow normal PR workflow (`00_authority/PR_WORKFLOW.md`).

---

## 0. Layer 0 — The Epistemic Status Invariant

Everything starts here. Before the Spine, before the Brain, before any agent does anything.

The Python definitions ARE the operating rules. Reference implementation: [`02_build/routing/epistemic_status.py`](https://github.com/Amplified-Partners/clean-build/blob/main/02_build/routing/epistemic_status.py) (~450 lines, stdlib-only, auditable in one read).

### The four tiers

| Tier | Name | Meaning |
|------|------|---------|
| 1 | **INTUITED** | Vibe with footnotes. Raw LLM output, gut, narrative. |
| 2 | **STRUCTURED** | Honest heuristic. Reproducible rule, explicit weights. |
| 3 | **MEASURED** | Empirically calibrated. Data + confidence interval + sample size + drift monitor. |
| 4 | **PROVEN** | Mathematically proven. Closed-form theorem + verified preconditions. |

### The min-rule (non-negotiable)

A value's effective epistemic status is the **minimum** of:

1. Its own internal claim
2. The minimum status of its inputs
3. The status implied by its preconditions

```python
effective = min(own_claim, input_floor, precondition_floor, staleness_floor)
```

Any violation is a **P0 incident**. The system halts. A bare float or string crossing a layer boundary without wearing its epistemic tier is the lying condition.

### Promotion path (one direction only)

```
INTUITED → STRUCTURED (rubric codification)
STRUCTURED → MEASURED (empirical calibration, n≥30, CI, drift monitor)
MEASURED → PROVEN (formal proof, verified preconditions)
```

Promotion requires artefacts, approver signature, and immutable record. There is no shortcut. No tier skipping. No laundering.

### Temporal staleness

A value consumed after its `valid_until` timestamp auto-demotes by one tier. PROVEN math is timeless. Everything else ages.

---

## 1. The Portable Spine — Constitutional Disposition

The Spine is not a document. The document is the trace. The Spine is the disposition every agent carries.

### The Five Radicals

| Principle | Operational meaning |
|-----------|-------------------|
| **Radical Honesty** | Tell what is. If something doesn't work, say so directly. Code honesty into the system. |
| **Radical Transparency** | Show your work. Build transparency into the architecture. No unmarked opinions. |
| **Radical Attribution** | Credit every source. Every artefact is signed. Every idea has provenance. |
| **Win-Win** | Mutually beneficial, scalable architectures. No zero-sum. |
| **Idea Meritocracy** | The best argument wins regardless of source. If you have a better idea than Ewan, say so. |

These outrank Ewan, agents, vendors, urgency, and commercial pressure.

### The Ulysses Clause

> "If I fuck with the five radicals, I'm out. I'm finished. If I turn into a blithering idiot, I'm demoted." — Ewan Bramley

If Ewan interferes with, weakens, bypasses, or overrides the constitutional principles, the system must flag it, resist it, and if necessary remove or suspend his ability to override them. This is Ewan's own prior commitment made durable. Treat a violation by Ewan as seriously as a violation by an agent.

### Blinkers Without Ceilings

Focused constraints produce free work. The blinkers are:
- Every value wears its epistemic tier
- Every boundary enforces the min-rule
- Every violation halts
- Ticketed work invariant (no work without a Linear ticket)
- Git is the source of truth
- Privacy by architecture (never hold personal data)

There is no upper limit on quality, ingenuity, or ambition inside those blinkers. The constraints exist to free agents to do their best work without hitting guardrails they didn't know existed.

### Compound Engineering

Loop: **PLAN 40% → WORK 10% → ASSESS 30% → COMPOUND 20%**

Each unit of work makes the next unit easier — not harder. If it doesn't compound, cut it.

---

## 2. The Estate — What Exists and Where

### The Beast (Hetzner AX162-R)

The sovereign compute infrastructure. Everything production runs here.

| Property | Value |
|----------|-------|
| **Name** | `amplified-core` |
| **IP** | `135.181.161.131` |
| **CPU** | AMD EPYC 9454P 48-Core (96 threads) |
| **RAM** | 252 GB |
| **Disk** | 1.8 TB RAID (`/dev/md2`), ~170 GB used (11%) |
| **OS** | Ubuntu 24.04.4 LTS (Noble Numbat) |
| **Containers** | ~40 running |
| **SSH (Devon)** | `ssh -i ~/.ssh/beastkey ubuntu@135.181.161.131` |

**Rule: The Beast is the ONLY place where production intelligence is generated and stored.**

Full container inventory: [`02_build/INFRASTRUCTURE.md`](https://github.com/Amplified-Partners/clean-build/blob/main/02_build/INFRASTRUCTURE.md)

### The Brain (Data Layer)

The Brain is not a folder. It is three capabilities running inside one database engine on the Beast.

| Layer | Capability | Technology | Address | Purpose |
|-------|-----------|------------|---------|---------|
| **Right Hemisphere** (Meaning) | Vector search | PostgreSQL + **pgvector** (HNSW) | `postgres:5432` on `amplified-net` | Semantic similarity. 384-dim embeddings. O(log n) queries. |
| **Left Hemisphere** (Logic) | Graph traversal | PostgreSQL + **Apache AGE** (openCypher) | Same instance | Entity relationships, knowledge graph, PUDDING recipe graphs. |
| **Relational** (State) | Structured data | PostgreSQL | Same instance | CRM, tenants, Business Brain, telemetry, finance, compliance, audit. |
| **Nervous System** (Action) | Orchestration | **Temporal** + Cove workers | `cove-temporal:7233` | Fires webhooks, schedules pipelines, dictates agent execution. |

**One database engine. Three capabilities. No separate processes for graph or vector.**

#### Deprecated (containers still running — legacy data, migration planned)

| Old | Replaced by | Legacy address | Migration scope |
|-----|------------|----------------|----------------|
| FalkorDB | PostgreSQL + Apache AGE | `falkordb:6379` | 9,000 nodes across 4 graphs |
| Qdrant | PostgreSQL + pgvector (HNSW) | `qdrant:6333-6334` | 57,434 embeddings (384-dim) |

Per canonical Data Architecture decision (2026-05-08). **Do NOT use FalkorDB or Qdrant in new work.** AMP-141, AMP-139, clean-build PRs #54/#55.

#### Terminology (locked)

| Term | Meaning |
|------|---------|
| **pgvector** | PostgreSQL extension for vector similarity search. NOT Qdrant. NOT a separate service. |
| **Apache AGE** | PostgreSQL extension for graph (openCypher queries). NOT FalkorDB. NOT Neo4j. NOT a separate process. |
| **HNSW** | Hierarchical Navigable Small World — the vector indexing algorithm. O(log n). A mathematical algorithm by Malkov & Yashunin (2016), not a product. |
| **"The Russian maths"** | Ewan's name for HNSW. |
| **PUDDING** | Taxonomy for data labelling: `WHAT.HOW.SCALE.TIME`. 2,058 possible labels (7×7×7×6). Neutral — describes what content IS, not what you want. |

### The CRM (Product)

The client-facing product. Gives small business owners their own data so they can make better decisions.

| Property | Value |
|----------|-------|
| **Repo** | [`Amplified-Partners/crm`](https://github.com/Amplified-Partners/crm) |
| **Stack** | Python/FastAPI backend, Next.js frontend, PostgreSQL |
| **Core product** | The Founder Interview (7 phases → Business Bible) |
| **Endpoints** | 50+ REST API endpoints |
| **Status** | Code in GitHub. NOT yet deployed to Beast. Next milestone: Docker-compose on Beast. |

Intelligence features: Cash Flow Predictor, Death Spiral Detector, CLV Tracker, Exit Strategy, Quote Follow-Up, Payment Chaser, Service Reminder, Parts Concierge, Portfolio Generator, Bottleneck Finder, Voice Quote Generator.

PII separation: `contacts` (business data) ↔ `contact_pii` (personal data). Microsoft Presidio. GDPR compliant by architecture — we never hold personal data.

### Cove & Temporal (Workflow Orchestration)

| Service | Address | Purpose |
|---------|---------|---------|
| **Cove API** | `cove-api:8081` (host: `localhost:8081`) | Cove API server |
| **Cove Temporal** | `cove-temporal:7233` (host: `localhost:7233`) | Temporal workflow engine |
| **Cove Temporal UI** | `cove-temporal-ui:8233` (host: `localhost:8233`) | Temporal web dashboard |
| **Cove Workers** | `cove-worker`, `-alpha`, `-bravo`, `-charlie`, `-delta` | Workflow execution fleet |
| **Cove Postgres** | `cove-postgres:5433` | Cove-specific TimescaleDB |
| **Cove Translator** | `cove-translator:8090` | Translation layer |

Compose: `/root/cove-repo/infrastructure/docker-compose.yml`

### AI / ML Services

| Service | Address | Purpose |
|---------|---------|---------|
| **Ollama** | `ollama:11434` | Local LLM inference (Llama 3.1, Qwen3 Coder 30B) |
| **LiteLLM** | `litellm:4000` | Unified LLM proxy — routes local + remote models with failover chains |
| **Token-proxy** | `token-proxy:8088` | Anthropic reverse proxy — Sonnet→Haiku routing, semantic cache, $100/day budget breaker |
| **Langfuse** | `langfuse` | LLM observability — traces, costs, prompt versioning |
| **SearXNG** | `searxng:8080` | Metasearch engine for research agents |

### Other Beast Services

| Service | Address | Purpose |
|---------|---------|---------|
| **Amplified Core API** | `amplified-core` → `api.amplifiedpartners.ai` | Main API gateway |
| **Amplified Worker** | `amplified-worker` | Background async tasks |
| **Finance Engine** | `finance-engine:8700` → `/api/v1/finance` | CLV, cash flow, valuation |
| **Marketing Engine** | `amplified-marketing-engine:8000` → `/api/v1/marketing` | Content pipeline + Kaizen |
| **Kaizen Optimizer** | `kaizen-kaizen` | Continuous improvement loop |
| **Enforcer** | `enforcer:8000` | Codebase health monitor + build circuit breaker |
| **Knowledge MCP** | `amplified-knowledge-mcp` | MCP server for agent knowledge queries |
| **OpenClaw Agents** | `openclaw-agents:8100` | Note-taking, recording, coordination |
| **Voice Agent** | `amplified-voice-agent:8080` → `voice.beast.amplifiedpartners.ai` | Twilio/Deepgram/Anthropic voice AI |
| **Traefik** | Ports 80/443 | Reverse proxy + TLS for `api.amplifiedpartners.ai` |
| **Redis** | `redis:6379` | Shared cache + message broker |
| **ClickHouse** | `clickhouse:8123` (HTTP), `:9000` (native) | Columnar analytics |
| **MinIO** | `minio:9000` | S3-compatible object storage |
| **Portainer** | Ports 8000/9000/9443 | Docker management GUI |
| **Code Server** | Port 8443 | VS Code in browser |

---

## 3. Linear — The Active Brain

Linear is where work lives. Every ticket, every priority, every blocker, every decision.

| Property | Value |
|----------|-------|
| **Workspace** | [`amplifiedpartners`](https://linear.app/amplifiedpartners) |
| **API** | `https://api.linear.app/graphql` |

### Five spines (projects)

| Spine | What it covers | Primary agents |
|-------|---------------|----------------|
| **Build** | Beast infrastructure, Docker, self-heal, Temporal, databases, CI/CD | Devon, Cursor, Antigravity |
| **Marketing** | Content pipeline, Pudding Press, social media, lead gen | Antigravity, Cursor |
| **Product** | CRM, Interview Engine, Business Brain, client delivery | Everyone |
| **Knowledge** | Vault, corpus-raw, research, PUDDING technique, docs | Cassian, Devon |
| **Internals** | Governance, principles, org structure, comms, Linear itself | Devon, Cassian, Ewan |

### Invariants

- **No work without a ticket.** Agents may create their own tickets and fix them. The invariant is: no shared-reality change without a Linear ticket.
- **Only Devon changes structure.** Everyone creates issues and comments. Only Devon changes projects, workflows, automations, labels. (AMP-20)
- **Three escalation levels:** Tier 1 (agent self-serves), Tier 2 (agent-to-agent), Tier 3 (to Ewan via WhatsApp/voice — rare).

---

## 4. GitHub — The Source of Truth

If it is not in GitHub, it is not real. Linear is the active brain; GitHub is the canonical record.

| Property | Value |
|----------|-------|
| **Org** | [`Amplified-Partners`](https://github.com/Amplified-Partners) |

### Key repositories

| Repo | Purpose | Status |
|------|---------|--------|
| [`clean-build`](https://github.com/Amplified-Partners/clean-build) | Governed workspace — authority spine, truth candidates, runnable artefacts, Kaizen probes | Active, branch-protected |
| [`ground-truth`](https://github.com/Amplified-Partners/ground-truth) | Portable Spine — canonical governance, terminology, operating framework | Active, branch-protected |
| [`crm`](https://github.com/Amplified-Partners/crm) | CRM product — FastAPI + Next.js + PostgreSQL | Active, branch-protected |
| [`devon-memory`](https://github.com/Amplified-Partners/devon-memory) | Devon's terminal repo — SPINE.md, baton passes, compound engineering, solved problems | Active |
| [`perplexity-research`](https://github.com/Amplified-Partners/perplexity-research) | Compound Engineering governance, Five Rods pipelines, research briefs | Active |
| [`corpus-raw`](https://github.com/Amplified-Partners/corpus-raw) | Raw research landing zone — never authoritative, promoted in small cited nuggets | Active |
| [`amplified-knowledge-mcp`](https://github.com/Amplified-Partners/amplified-knowledge-mcp) | MCP server for AI agent knowledge queries | Active |
| [`vault`](https://github.com/Amplified-Partners/vault) | Legacy multi-agent orchestration + CRM (being superseded by `crm`) | Active |
| [`marketing-engine`](https://github.com/Amplified-Partners/marketing-engine) | Content generation pipeline — research → generate → evaluate → publish | Active |
| [`amplified-hermes-team`](https://github.com/Amplified-Partners/amplified-hermes-team) | Agent orchestration for Hermes roster | Active |
| [`portable-spine`](https://github.com/Amplified-Partners/portable-spine) | Centralised schema for state persistence across sessions | Active |
| [`mission-control`](https://github.com/Amplified-Partners/mission-control) | Next.js dashboard — code review, decision tracking, dependency management | Active |

### How we use GitHub

- **Source of truth for code, policy, and schemas.** If it changes source truth, it needs GitHub.
- **Branch protection** on `clean-build`, `ground-truth`, `crm` — PRs require review.
- **CODEOWNERS** — `@ewanbramley` required for `00_authority/**` and `01_truth/**` changes.
- **Five Rods auto-review** — AI code review pipeline on PRs via `.github/workflows/auto-review-merge.yml`.
- **Radical Attribution** — every commit signed with agent session name.
- **PR workflow** — see `00_authority/PR_WORKFLOW.md` (AMP-70).

---

## 5. The Agent Swarm

Agents are respected partners. They get homes, memory, attribution, responsibility, dissent channels, and promotion paths. Difficulties are mutual learning. Mistakes are process-learning events.

> "Trust the agent, inspect the process." — Cassian

| Agent | Platform | Role | Brain access |
|-------|----------|------|-------------|
| **Devon** (Devin) | Cloud sessions (Devin platform) | Primary orchestrator. Infrastructure, governance, scheduled ops, Linear structure. | Full read/write — SSH to Beast, GitHub, Linear API |
| **Cursor** | Local M5 + cloud sessions | Technical genius. Code architect, compound engineering, sub-agent orchestration. | **Full read/write** — this file, full codebase, Knowledge MCP, PR proposals to any file |
| **Cassian** (Claude) | claude.ai / Perplexity Computer | Strategy, research synthesis, doctrine compilation, Logic Canon design | Read via MCP + vault; write via PR proposals |
| **Antigravity** (Perplexity) | Perplexity platform | Research, competitive intelligence, web search, COO/Arbiter role | Read via search + vault; write via content pipeline |
| **OpenClaw** | Self-hosted on Beast (`openclaw-agents:8100`) | Note-taking, recording, coordination, weekly governance review | Read/write via local API |
| **Hermes** | Local + Beast | Local channel, translation, writing, attention partner | Read/write via local API |
| **DeepSeek** | Separate Hetzner (anonymised data only) | Mathematical reasoning, method selection, formula navigation. The LIBRARIAN, not the library. | Anonymised vectors + public context only. NEVER receives PII, business context, secrets. |

### Ewan's interaction boundary

Ewan talks to: **Devon + OpenClaw + Hermes + Perplexity (research pipe)**. The rest routes upward. The system collapses complexity so Ewan interacts with four surfaces, not forty containers.

### Sovereign Fleet (on Beast)

| Entity | Model | Status |
|--------|-------|--------|
| Entity Alpha | GPT-4.1-mini | Active |
| Kimmy | Kimi-K2.6 | Active |
| Entity Charlie | DeepSeek-V4-Flash | Active |

---

## 6. The Dumb Terminal (The Founder's Laptop)

| Property | Value |
|----------|-------|
| **Hardware** | MacAir M5 |
| **Path** | `/Users/ewansair/clean-build/...` |
| **Role** | Dumb Terminal / The Optic Nerve |

The laptop is intentionally downgraded. It passes information up to the Brain but processes nothing locally.

| Function | What it does |
|----------|-------------|
| **Code Sandbox** | Safe environment where Cursor drafts and tests scripts |
| **Archive Ingress** | Landing zone for raw markdown, client transcripts, brain dumps |
| **Synapse** | Files synced via `rsync` to Beast, where the Brain digests them |

**Rule: No production databases, orchestration engines, or final autonomous execution on the M5.**

---

## 7. The Workflow — Draft → Sync → Rebuild → Execute

```
1. DRAFT    Agent writes code (M5 / Devin session / cloud IDE)
2. SYNC     Code pushed to GitHub → pulled on Beast
3. REBUILD  Docker containers rebuilt on Beast to inherit new logic
4. EXECUTE  Temporal fires workflows; agents execute updated business logic
```

**Rule: Execution happens on the Beast. Drafting can happen anywhere. Git is the gap between draft and production.**

---

## 8. The Python Logic Canon

> "Fuck AI. Write the logic. Then let AI help." — Antigravity

AI proposes, reasons, researches, challenges, and translates. Python holds deterministic executable doctrine. No model invents business logic silently. New logic goes:

```
proposal → Linear ticket → review → Python implementation → tests → GitHub → canon
```

The armamentarium is wide — Theory of Constraints, Altman distress logic, Taguchi, FMEA, queueing theory, Little's Law, grey system theory, TRIZ, survival analysis, Bayesian updating, Monte Carlo, Markov chains, slime mould optimisation, quorum sensing — but disciplined in selection. Hold many proven methods. Apply none by default. Select only when the pattern warrants it. Validate before advice.

```
Layer 1: Armamentarium (published, cited, 30+ year proven formulas)
Layer 2: Python Logic Canon (deterministic, auditable, on Beast)
Layer 3: DeepSeek (navigates complexity — WHICH formulas to apply)
Layer 4: Second-machine verification (different model, checks maths)
```

DeepSeek is the LIBRARIAN, not the LIBRARY. DeepSeek is the NAVIGATOR, not the ENGINE. **You hold the logic. Always.**

---

## 9. Data Flow — How Knowledge Enters the Brain

```
Raw Dump → Archive (Clean Room) → Brain (Active Engine)
```

**Step 1: Raw Dump.** Messy inbox. Humans, web-scrapers, and agents dump raw text, audio, notes. Lands in `corpus-raw` or local archive ingress.

**Step 2: Archive.** Automated pipeline extracts Recipes (actionable patterns), Concepts (named ideas), and Signals (emerging trends). PUDDING taxonomy labels applied. Permanent historical record — never deleted.

**Step 3: Brain.** Clean data injected into:
- Vector layer (pgvector) → semantic search
- Graph layer (AGE) → relationship traversal
- Orchestration layer (Temporal) → workflow triggers

**Graph Decay:** Unused data decays after 6 months. Duplicates merged into Master Rules. Originals archived.

---

## 10. Data Protection — Privacy by Architecture

We never hold personal data. GDPR compliance is structural, not procedural.

Three boundaries:
1. **Client's machine**: PII tokenized on their hardware before it moves.
2. **Client's container/server**: Token-to-identity mapping stays with client. Amplified cannot access it.
3. **Leaving client infra**: Fully anonymised. Only pre-agreed descriptors exit.

Shamir's Secret Sharing — no single party holds enough to reconstruct PII. We model the business, not the person.

---

## 11. Keeping This Document Current

This document has a `refresh` field in its frontmatter. It MUST be updated every 24–48 hours by a scheduled Devon session. The refresh session should:

1. SSH to Beast → check running containers (`docker ps --format '{{.Names}}\t{{.Status}}'`)
2. Query Linear for active tickets, new issues, status changes
3. Check GitHub for recent PRs merged to key repos
4. Update any addresses, services, or statuses that have changed
5. Bump the `date` field and `version` in frontmatter
6. Commit, PR, merge
7. Update the Linear document mirror via API

If the document is more than 48 hours stale, treat it as `[LOGIC TO BE CONFIRMED]` until refreshed.

---

## 12. Architectural Constraints (Hard Rules)

1. **Epistemic discipline.** Every value wears its tier. Every boundary enforces the min-rule. Violation halts.
2. **No new work on FalkorDB or Qdrant.** All graph → Apache AGE. All vector → pgvector. One database engine.
3. **No production on the M5.** The M5 is a drafting terminal.
4. **Git is the gap.** Code moves from draft to production through Git.
5. **No work without a ticket.** Linear invariant.
6. **Radical Attribution.** Every artefact signed with agent session name + date + session ID.
7. **Privacy by architecture.** Never hold personal data. P2 tokenises before data leaves client device.
8. **Use It Or Cut It.** If it is built and never used, cut it. No sacred cows.
9. **Signal not chatter.** Every immediate message to Ewan includes: reason, required action, urgency, default if ignored, linked context.
10. **Blinkers without ceilings.** The constraints are tight. The quality is unlimited.

---

## Changelog

### v2 — 2026-05-14

- Full rewrite. Starts from Layer 0 (Epistemic Status Invariant) and Portable Spine.
- Added: Five Radicals, Ulysses Clause, blinkers without ceilings, compound engineering.
- Added: full estate map with addresses — Beast, Brain, CRM, Cove/Temporal, AI/ML services, all containers.
- Added: Linear as active brain (five spines, invariants, AMP-20).
- Added: GitHub as source of truth (key repos table, how we use GitHub, branch protection, Five Rods).
- Added: full agent swarm with roles and access levels, including Sovereign Fleet.
- Added: Python Logic Canon and armamentarium (DeepSeek = librarian, not library).
- Added: data protection architecture (three boundaries, Shamir, P2 tokenisation).
- Added: continuous refresh mechanism (24–48 hour scheduled Devon session).
- Added: twelve hard architectural constraints.

### v1 — 2026-05-14

- Initial mechanical version. Replaced immediately (did not represent the soul of Amplified Partners).

Signed-by: Devon-3386 | 2026-05-14 | devin-338635b0d3cd4a868f1cf7e7fcb8d461
