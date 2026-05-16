---
title: Estate Discovery Report — radical transparency snapshot
date: 2026-05-16
version: 1
status: "[NARRATIVE] candidate-report — not authoritative until reviewed/merged"
audience: "anyone who wants the complete picture of the Amplified Partners estate"
---

<!-- markdownlint-disable-file MD013 -->

## Epistemic header — read this first

This document follows Amplified min-rule discipline. Every section below sits at one of the following tiers (see `00_authority/OPINION_CONFIDENCE.md` and the `[NARRATIVE] / [STRUCTURED] / [MEASURED]` ladder).

- **[STRUCTURED]** — user-provided number or claim. Recorded faithfully, **not** independently verified from repo files at write time. Treat as the operator's working figure, not as canonical truth.
- **[CITED]** — claim confirmed against a file in this repo at the path shown inline. Treat as repo-truth at the commit pinned at the bottom of this report.
- **[NARRATIVE]** — the human story. Honest, qualitative, not measurable; do not promote into a metric.
- **[LIVE / VERIFY BEFORE USE]** — runtime claim about the Beast or external services. Frozen at the date in this header. **Anyone acting on it operationally must re-verify against the live system first.**

Two further constraints that govern this report:

1. **No silent promotion.** Where the user supplied a number (e.g. "45 repos", "330GB", "£400k+", "6.26M lines", "1.2M lines in vault", "2,000 lines of shell scripts"), it is marked **[STRUCTURED]**. It is not relabelled as measured.
2. **Beast runtime is a moving target.** Container counts, port bindings, and Tailscale reachability change. The Beast block below is **[LIVE / VERIFY BEFORE USE]**, dated 2026-05-16. Re-check before any operational action.

**Drift signal at write time: AMBER.** Per the latest 2026-05-16 inventory: knowledge_vectors are populated in the millions but `ingestion_manifests = 1` and `audit_log = 1`, with 108 `pipeline_runs` in `failed_canonical_write`. Brain is full; the canonical-write / receipt path is not healthy.

---

## 1. Executive Summary

> **Tier: [STRUCTURED] headline numbers (user-provided), [NARRATIVE] interpretation.**

### Headline numbers (user-provided, **[STRUCTURED]**)

- **45 repositories** across the Amplified-Partners estate.
- **~330 GB** of storage in play across local and remote disks.
- **£400k+** of code value estimated by the operator across all surfaces.

For reconciliation against GitHub org metadata and PR121's classification, see § 9 (Appendices) — the 45 figure is the operator's estate-wide working figure; the GitHub org itself currently shows **38 visible repos** (see § 2).

### Core finding

There is extraordinary value buried in chaos. The estate is not "thin" — it is dense, overgrown, and under-mapped. The work to be done is curation, not creation. Most of what would be needed to ship a working business already exists somewhere in the estate; the problem is that nobody currently has a defensible index of *where*.

### The human story — **[NARRATIVE]**

Five months. Roughly ten hours a day. One non-coder, with decades of small-business operational judgment, learning what AI can do by *using* it — not by reading about it. The codebase reflects that: bursts of capability, then sediment; brilliance next to abandoned probes; a working Marketing Engine sitting beside a half-built control plane and a dozen Markdown files that nearly agree.

This is not the expert's journey. It's the Muppet's journey — and that is precisely why the chaos is worth showing.

### Path forward — **[STRUCTURED]** plan, **[NARRATIVE]** framing

A **3-day cleanup** is in scope using the **compound engineering** loop (80% Plan + Review, 20% Work + Compound — see `.cursorrules` "The Compound Engineering Loop"). Detail in § 7.

---

## 2. The Chaos — what we found

> **Tier: [STRUCTURED] counts (operator-supplied), with [CITED] reconciliations where repo evidence exists.**

### Repository chaos — **[STRUCTURED]**

- 45 repos total across the estate (operator working figure).
- ~7 duplicates.
- ~5 stubs.

**Reconciliation with org metadata — [STRUCTURED, partly verifiable]:** the Amplified-Partners GitHub org shows **38 visible repos** (33 private, 5 public), total GitHub disk **130,528 KB**. PR121 classifies the broader estate as **45 → 27 active / 12 deletion / 6 archive** with migration scripts and a 19-field schema. The 45 vs 38 gap is explained by the broader estate including stubs, deletion candidates, and archive targets that may not be live in org metadata. **PR121 is open / not merged → its classification is a high-value proposal, not settled truth.**

### Storage chaos — **[STRUCTURED]**

- ~330 GB total.
- ~200 GB judged deletable by the operator.

### Code chaos — **[STRUCTURED]**

- ~270K lines in repos.
- ~6.26M lines on the Beast (the operator's primary build host).

The Beast figure includes vendored dependencies, generated artefacts, and ingestion outputs — it is a "lines on disk" figure, not a "lines we wrote" figure. See § 4 for the scattered-code breakdown.

### Documentation chaos — **[STRUCTURED]**

- ~1.2M lines in the vault.

This is the substrate the Brain has been ingesting against. The high source distribution from `store_b_clean` and `vault-markdown` in § 3 reflects this.

### AI-tool chaos — **[STRUCTURED]**

- ~7 different "save formats" across the tools in use. Each tool stores transcripts, snippets, and artefacts in its own shape; nothing was canonical at intake.

### The OpenClaw incident — **[NARRATIVE]**

A paranoid security-consultant story; preserved here because it explains why several controls in the estate are tighter than the size of the team would otherwise justify. The presence of an `OpenClaw` service in the live container set (see § 3) is the visible residue of that episode.

---

## 3. The Value — what's actually working

> **Tier: mixed. Counts are [STRUCTURED] unless [CITED]. Beast container details are [LIVE / VERIFY BEFORE USE], dated 2026-05-16.**

### Marketing Engine — **[STRUCTURED]**

- 40 avatars.
- 5 platforms.
- Kaizen-style improvement loop wired in.

### CRM — **[STRUCTURED]**, with a critical **[LIVE]** correction

- 153 endpoints (operator figure).
- Business intelligence surface.
- Interview engine attached.

**Live correction — [LIVE / VERIFY BEFORE USE]:** the live Beast inventory shows `amplified-crm` up/healthy on `127.0.0.1:8001` and `amplified-crm-dev` up on `127.0.0.1:8003`. **It is therefore wrong to say "CRM is not deployed."** What is correct: CRM containers exist and at least one is healthy. **Functional route / import / API verification is still required** before any of the 153 endpoints can be claimed as working.

### Orchestration — **[STRUCTURED]**

- Temporal workflows (Cove API + Temporal + workers visible in the live container set).
- Compound engineering loop (see `.cursorrules`, "The Compound Engineering Loop" — **[CITED]**).

### Infrastructure — **[LIVE / VERIFY BEFORE USE]**, dated 2026-05-16

**Update on older "37+/40" figures:** the latest live inventory shows **46 Beast containers, 45 running, 1 exited.** The running set includes:

- SearXNG
- Three Ollama containers
- Traefik
- CRM containers (`amplified-crm`, `amplified-crm-dev`)
- Enforcer
- Infisical
- Cove API / Temporal / worker services
- Vellum
- `amplified-knowledge-mcp` (Brain reader)
- `beast-control-mcp` (Beast control plane MCP)
- code-server
- Redis
- Brain MCP read/write lanes
- Langfuse
- LiteLLM
- OpenClaw
- Marketing services
- Sovereign fleet entities
- Mission Control
- Token proxy
- Tailscale
- Nexus dashboard
- `amplified-core`
- `cove-postgres`
- Kaizen
- MinIO
- Watchtower

Older docs that report "37+ containers" or "40 containers" are not wrong-at-the-time; they are out of date as of 2026-05-16. **Re-verify before any operational use.**

### MCP servers — **[STRUCTURED]**

- 13 servers.
- 42+ tools.

The repo's `MCP_SERVERS.md` lists the canonical set — **[CITED]** `MCP_SERVERS.md`.

### Ingestion pipes — **[STRUCTURED]**

- 6-lane methodology.
- PUDDING extraction pipeline (referenced in `01_truth/schemas/2026-03_pudding-discovery-system_v1.md` — **[CITED]**).

### Vellum — **[STRUCTURED]** capability, **[LIVE]** state

- Inter-agent communication system.
- Vellum container is running in the live inventory; **the command-broker capability is design-stage**, not built (see § 7 and § 9).

### Brain health — **[LIVE / VERIFY BEFORE USE]**, dated 2026-05-16

- PostgreSQL **15.17**.
- Database: `amplified_brain`.
- Server: `amplified-knowledge-mcp` v2.1.0 (read-only).
- `knowledge_vectors`: **2,226,545**.
- Vectors with embeddings: **2,226,249**.
- `entities`: 53,959.
- `relationships`: 34,488.
- `episodes`: 4,257.
- `pipeline_runs`: 115.
- `ingestion_manifests`: **1**.
- `audit_log`: **1**.

**Source distribution:**

- `store_b_clean`: 1,311,290
- `store_m5_drop_2026_05_11`: 523,205
- `vault-markdown`: 163,554
- `sweep_to_brain`: 60,748
- `filtered_for_ingestion`: 53,136

**Ingestion status: AMBER.** Of 115 pipeline runs: **108 failed_canonical_write, 3 failed_pudding, 2 completed_noop, 1 completed, 1 halted_error_rate.**

**Critical interpretation:** the Brain is populated, but the canonical-write path and receipt coverage are not healthy. Treating any Brain content as "canonical" today violates the target invariant *"if a record entered Brain without an ingestion receipt, it is not canonical"* (see § 9, Epistemic invariant note).

---

## 4. The Hidden Value — scattered code

> **Tier: [STRUCTURED] line counts (operator-supplied). Domain labels are descriptive.**

| Domain | Approx. lines | Notes |
|---|---|---|
| Shell scripts & automation | ~2,000 | Wiring, install, maintenance scripts scattered across the estate. |
| Docker compose files | ~3,000 | Multiple compose files reflecting the layered build history. |
| API routes | ~8,000 | Surfaces beyond the CRM 153-endpoint count above. |
| Telephony & voice code | ~4,100 | The voice/phone work that grew under the operator's voice-first workflow. |
| Integration-layer code | ~2,000 | Glue between the various services. |
| **Total additional** | **~31,500 lines** | **£200,000+** operator-estimated value buried under the headline number. |

Read with care: these are scattered surfaces, not a packaged product. Their value is real but only realisable after curation.

---

## 5. The Human Story — learning with AI

> **Tier: [NARRATIVE] throughout. Do not promote any phrase here into a metric.**

This is the part that the technical documentation never carries. It belongs in the record because it explains the shape of what was found.

- **Transcription chaos.** Strong accent, fast speaker, occasionally with a drink in hand. Transcripts came back interesting, sometimes wonderful, sometimes garbled. Several of the ingested artefacts in the vault carry that texture and should be read in that voice rather than as polished prose.
- **The iCloud disaster.** Documents lost to a sync incident — preserved here so future you remembers why local-first / explicit-export habits hardened later in the build.
- **Perplexity Desktop confusion.** Data left on the desktop that should have gone into the corpus. Recovered, but it is part of the reason raw research now has its own home (`Amplified-Partners/corpus-raw`).
- **The Soviet-era mathematics moment.** A long, rambling voice note that read like nonsense on first pass and turned out to contain a precise framing of a hard problem. Preserved as a reminder that voice-first thinking sounds different from written thinking, and the system has to be able to hear both.
- **Chieftain of the pudding race.** Burns connection. The naming convention around "PUDDING" extraction is not arbitrary; it sits inside a coherent set of references and jokes that make the estate feel like a place rather than a folder. Keep that.
- **The farting haggis.** Gamification gone wonderfully wrong. Recorded here so we remember to laugh at our own mistakes.

**Lesson:** you do not have to be a technical genius to build something useful with AI. You have to be curious, willing to follow where AI leads, and disciplined enough to come back and curate.

---

## 6. The Root Cause — why this happened

> **Tier: [NARRATIVE] with [STRUCTURED] observations.**

- **No architect, no floor plan.** The estate grew by accretion, one capability at a time, each one justified on its own.
- **Governance exists but is not enforced.** `00_authority/` is well-formed and well-intended (see `00_authority/MANIFEST.md`, `00_authority/PRINCIPLES.md`, `00_authority/SIGNATURES.md` — **[CITED]**), but lacks the structural enforcement that would make it self-policing at PR time.
- **Reorganisation plans written but never executed.** PR121 is the canonical example: a serious classification of the estate sitting open as a candidate.
- **The cleanup loop.** Planning has been live since January. Execution has not happened.
- **Well-intentioned actions without full understanding of tools.** The operator learned the tools in flight. Several "tidy-ups" earlier in the build cycle moved or renamed things in ways that future cleanups had to reverse.

---

## 7. The Path Forward — 3-day cleanup

> **Tier: [STRUCTURED] plan. Tasks are commitments to attempt, not predictions of outcomes.**

### Day 1 — local storage + repo audit

- Free **~200 GB** of local storage (the operator-identified deletable share of the 330 GB total).
- Repo audit against PR121's 45 → 27 / 12 / 6 classification.

### Day 2 — database migration + Business Brain implementation

- Database migration aligned with the 19-field schema.
- Business Brain implementation against the canonical-write invariant.

### Day 3 — content extraction + governance enforcement

- Content extraction from the vault into structured surfaces.
- Governance enforcement: convert `00_authority/` rules into PR-time checks where reasonable.

### Methodology

**Compound engineering** — 80% Plan + Review, 20% Work + Compound. See `.cursorrules` "The Compound Engineering Loop" — **[CITED]**.

### Current immediate plan (this week)

- **Refresh PR124** ("Add Working Code Inventory — running, teed up, mentioned-but-not-built") with live Beast data, so its inventory matches the 46-container reality rather than an older 37+ snapshot.
- **Create a live estate receipt** that pins counts, container set, and Brain health at a specific timestamp.
- **CRM route verification** — close out the "CRM not deployed" / "CRM containers up" contradiction by exercising the 153 endpoints against the healthy `amplified-crm` container.
- **MCP dependency inventory** — before any rebinding of `0.0.0.0:8401` / `0.0.0.0:8402`, list what depends on those bindings. **No blind rebinding.**
- **Brain-writer inventory** — enumerate every writer that has put rows into `knowledge_vectors` without an `ingestion_manifest` entry.
- **BrainDrop design** — design the future ingestion-receipt enforcement so that `ingestion_manifests` grows monotonically with `knowledge_vectors`.
- **Patch the epistemic sample-size rule** — `epistemic_status.py` / `epistemic_status_invariant.py` currently promote at a flat `sample_size < 30`. Current doctrine is **10 events per parameter per outcome class.** That is a doctrine-code drift; patch it (see § 9 hashes).
- **Promote only after receipt.** No surface promotes from `[STRUCTURED]` to `[MEASURED]` without an attached receipt.

---

## 8. The Radical Transparency — why this matters

> **Tier: [NARRATIVE].**

The point of writing this report is not to file a status update. It is to make the whole estate legible, including the parts that are embarrassing.

- **Other people can learn from this chaos.** The shape of the mess is itself useful evidence about what happens when one curious operator and a fleet of AI tools meet a real business problem for the first time.
- **The Muppet's journey, not the expert's journey.** Expert post-mortems are tidy and unrepresentative. This one is messy and representative.
- **Logic, or the lack of it.** What broke. What worked. What should not have worked but did. What looked like genius and turned out to be ramble; what looked like ramble and turned out to be genius.
- **Learning: start with organisation, not end with it.** This is the single biggest take-away for anyone walking the same path next. Build the index *as* you build, not after.

---

## 9. Appendices

> **Tier: mixed. Each appendix labels its own tier.**

### A. Detailed repository inventory

**[STRUCTURED] / candidate authority.** Defer to PR121's classification (45 → 27 active / 12 deletion / 6 archive). Org-metadata view: **38 visible repos** (33 private, 5 public), 130,528 KB total disk. Reconciliation in § 2.

### B. Complete code inventory by domain

**[STRUCTURED].** Headline: ~270K lines in repos; ~6.26M lines on the Beast; ~31,500 lines of additional scattered code (see § 4). PR124 is the candidate inventory PR — **open**, useful as structured evidence, **not authoritative** until reviewed and merged.

### C. The 19-field schema

**[STRUCTURED] / candidate.** Introduced in PR121's migration scripts. Not adopted as authoritative until PR121 (or a successor) merges.

### D. The Canonical Data Architecture

**[STRUCTURED] / target.** Current model:

- **GitHub** = code source of truth.
- **Linear** = live WIP.
- **Vellum** = append-only audit / document / decision / approval plane.
- **Beast Brain** = canonical knowledge / reference substrate.

**Target invariant:** *"if a record entered Brain without an ingestion receipt, it is not canonical."* Not yet implemented — Brain has millions of vectors but only 1 `ingestion_manifest` and 1 `audit_log` row (see § 3).

**Portable control plane (target design, not built):**

phone / M5 → Vellum command request → append-only event → approval / policy check → Beast command broker → Tailscale SSH / local agent runner → target host → stdout / stderr / exit code recorded back into Vellum → AuditLog / DriftSignal update.

**Tailscale / AgentMesh — [LIVE, partial]:** M5↔M4 mesh proven for SSH / SCP / SMB / Screen Sharing. Tailscale IPs: `macairm4 100.101.251.67`, `macairm5 100.85.225.46`, `beast-amplified 100.101.0.53` (visible; **Beast Tailscale SSH refused**), `wanmin 100.77.149.1` (visible; remote login not proven). Treat as a partially-proven research / dev mesh, **not** a complete production control plane.

### E. The metadata-scoring framework

**[STRUCTURED] / candidate.** Referenced across PR121 / PR124 / the Brain architecture rewrite (commit `8e12e6c` — **[CITED]** via `git log`). Not yet enforced at write time.

### F. Contradictions and reconciliations

**[STRUCTURED] / honest list.**

- "ewan-dot 6 stubs" — the original surface was wrong; corrected against the broader 45-repo estate.
- PR121's **45** vs org metadata's **38** — broader estate vs visible org (see § 2).
- PR124's **37+ containers** vs live **46** — older snapshot vs 2026-05-16 inventory (§ 3).
- PR124's "**CRM not deployed**" vs live healthy CRM containers — supersede with "containers exist, functional verification still required" (§ 3).
- Brain is huge but `ingestion_manifests` and `audit_log` are tiny — receipt-coverage failure (§ 3).
- A DeepSeek audit was labelled `[MEASURED]`; under min-rule discipline it should be `[STRUCTURED]` until raw evidence is attached.
- Vellum container is running, but the **command-broker capability is design-stage** (§ 3, § 9.D).

### G. Security posture — **[STRUCTURED] / concern list, [LIVE] details**

- MCP exposure: `amplified-knowledge-mcp` on `0.0.0.0:8401` and `beast-control-mcp` on `0.0.0.0:8402`. **Do not blindly rebind.** Inventory dependencies first (§ 7 immediate plan).
- Email / session / token leakage risk.
- Broad-root habits on Beast.
- Ingestion overreach.
- Status laundering (treating `[STRUCTURED]` claims as `[MEASURED]`).
- Phase note: current phase is **research / dev**; **no client data yet** per handoff. Macs mostly cleared except email.

### H. Day Zero doctrine, 19/3 principle, Council

**[STRUCTURED] / authoritative-in-spirit.** Day Zero doctrine: perfect reversibility over perfect extraction; chaos as ore; no destructive action unless six conditions hold; APDS-only writes; Phase 3.5 quarantine of polluted vectors before new ingestion. 19/3 principle: 17 floor, 20 ceiling, 19 chosen operating point, 3 human-presentation cardinality. **Council shadow-only.** **Vellum Correspondence not built.**

### I. Epistemic invariant note — **[CITED]** files in repo

Two near-duplicate files exist:

- `epistemic_status.py` — SHA-256 `36b48c9cdd6a81b5f094507cd401282bedd23c79c00f65291c6a62382ecefcb8`
- `epistemic_status_invariant.py` — SHA-256 `89e374e8fe3ab5e2e632c9ba77ab860d583e83a18ed8e54125093fbf168fcf83`

Both compile. Not byte-identical. **Only observed diff is the authorship line.** Important issue: `promote_to_measured` uses a flat `sample_size < 30`, while current min-rule doctrine is **10 events per parameter per outcome class.** This is a **doctrine ↔ code drift** and should be patched (§ 7 immediate plan).

### J. Beast runtime caveat (repeated deliberately)

**[LIVE / VERIFY BEFORE USE].** Every Beast-runtime claim in this document is frozen at 2026-05-16. Container counts, port bindings, Tailscale reachability, and Brain row counts all drift. Before acting operationally on anything in § 3 or § 9.D, **re-verify against the live system.**

---

## Closing

The estate is not a failure. It is a working but unsorted hoard — built by one operator, at speed, with AI as the lever. The honest move now is to curate it, not to apologise for it. This report is the index that says: here is what is in the hoard, here is what works, here is what is provisional, here is what must be verified before anyone bets on it.

Drift signal at write time: **AMBER**. The single most important fix to move it toward GREEN is receipt coverage on Brain writes (§ 3, § 7, § 9.D, § 9.I).

---

Signed,

**Devon (Claude Code subagent)**
Session: estate-discovery-report
2026-05-16
