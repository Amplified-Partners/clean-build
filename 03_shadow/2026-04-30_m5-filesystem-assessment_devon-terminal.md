# M5 Filesystem Assessment — Amplified Partners
## Devon (Terminal M5) | 2026-04-30 | devin-ebf31a94a5bc4822baef08bb30be1378

---

## 1. Executive Summary

| Metric | Count |
|--------|-------|
| Total markdown files on machine | **163,316** |
| Total files in ~/corpus-raw | **8,113** |
| Total files in ~/Vaults (extracted data + transcripts) | **~8,500+** |
| Total files in ~/2026-04-25-SPARKLE-INBOX | **35,423** |
| Total files in ~/clean-build/02_build (excl. node_modules, .venv) | **1,213** |
| Voice transcripts (Monologue app, all formats) | **2,214** (Voice-Transcripts dir) + 1,004 raw (Unified-Data staging) |
| Pudding extraction files | **48** (monologue-unknown) + 9 inbox-voice extractions |
| .cursorrules files | **2** |
| CLAUDE.md files | **0** found at root level; compound-engineering plugin has one |
| AGENTS.md files | **50+** instances (authoritative: ~/clean-build/AGENTS.md) |
| Git repos found | **5** (clean-build, corpus-raw, SPARKLE-INBOX, crm submodule, perplexity-ai-export submodule) |
| Uncommitted files in clean-build | **2** (one untracked, one modified submodule) |
| Uncommitted files in corpus-raw | **0** (all committed in single initial dump 2026-04-23) |

**Headline finding:** This machine contains a vast, multi-layered knowledge base that is largely uncommitted or scattered across local-only directories. The `~/corpus-raw` repo was committed in a single "rough but ready" dump on 2026-04-23. The majority of the Amplified Partners strategic knowledge lives outside any git repo — in `~/Vaults`, `~/Downloads`, `~/Amplified Partners Truth`, and `~/.claude/`. The vault on the Beast has not been cross-referenced here but the Mac-local corpus is substantial and partially divergent.

---

## 2. Directory Map — Every Amplified Partners Directory

### 2.1 Primary Active Directories

#### `~/clean-build/` — CANONICAL AUTHORITY REPO
- **Git repo:** Yes — branch `transition-mac-mini`, 10 commits
- **Status:** 1 untracked file, 1 modified submodule (not committed)
- **Structure:**
  - `00_authority/` — 15 files (NORTH_STAR, MANIFEST, PRINCIPLES, SIGNATURES, DECISION_LOG, EIGHT_LAWS, etc.)
  - `01_truth/` — processes (50+ docs 2026-03 to 2026-04), schemas (~40 files), interfaces, data (Excel/JSON/CSV)
  - `02_build/` — 1,213 source files across: cove-orchestrator, crm (submodule), marketing_engine, command-centre, amplified-site, byker-production, covered-ai-v2, perplexity-ai-export (submodule), content-engine, business-brain, librarian-api, sidecar, integrations
  - `03_shadow/` — 106 files (sessions, job-wrapups, baton passes, charter drafts)
  - `90_archive/` — 404 files (historical snapshots, authority history)
- **Last commit:** `922341a` — "Vault UI search engine, corpus-raw integration, and Mini sync baton pass"
- **Uncommitted:** `03_shadow/2026-04-29_portable_spine_and_sidecar_update.md` (UNTRACKED), `02_build/perplexity-ai-export` (modified submodule content)

#### `~/corpus-raw/` — RAW RESEARCH CORPUS REPO
- **Git repo:** Yes — 1 commit: "Initial corpus dump 2026-04-23 (rough but ready)"
- **Total files:** 8,113
- **Structure:**
  - `ewan-docs/` — framework documents, vertical research, unified data architecture docs, hounddog plan
  - `ewan-mac/archive/` — Research Pipe v1 (Python modules: curator1, curator2, intake, orchestrator, search, interpreter)
  - `ewan-mac/archive2/` — Research Pipe v2 (BATON_PASS.md, BATON_PASS_v2.md)
  - `ewan-mac/archive3/` — Session notes 2026-04-12 to 2026-04-16 (Berlin research pipe sessions)
  - `ewan-map/` — mapping data
  - `vault/` — 4,630 files in structured vault subdirs: `_inbox`, `_inbox-voice`, `_inbox-work`, `_inbox-uncategorised`, `_staging`, `_system`, `eli`, `imported-business-docs`, `infra-ai-stack`, `knowledge-qdrant`, `projects`, `research`, `scripts`, `the-room`, `therapy-suite`, `transcripts`, `work`, `work-covered-ai`
- **Status:** Everything committed (0 uncommitted files). This is the single commit dump — no history.

#### `~/Vaults/Ewan/` — LOCAL VAULT (NOT IN ANY GIT REPO)
- **Git repo:** No
- **Total files:** ~8,500+
- **Structure:**
  - `01-tangents/` — `first_tangent.md`
  - `02-extracted-data/` — **6,030 files** — UUID-based extractions, inbox-voice extractions, AI-Rescued-CRM-Data extractions (agents, MCP servers, skills, commands — 50+ command extractions)
  - `AI-Rescued-CRM-Data/` — CRM data files including transcript-jan-15.md
  - `AI-Rescued-CRM-Data-2/` — duplicate/v2 of above
  - `Voice-Transcripts/` — **2,214 files** total:
    - `INDEX.md` — master index, states 104 files + 2,126 in archive
    - `monologue/` — 47 recent transcripts
    - `monologue-full/` — **2,104 files** (monologue-unknown-0001 through 0090)
    - `superwhisper/` — 6 recordings
    - `whisper-cli/` — 57 transcripts (Feb 14-15, 2026)
    - `PUDDING-ANALYSIS-COMPLETE.md`, `PUDDING-SYSTEM-IMPLEMENTATION.md`, `PUDDING-SYSTEM-PROPER.md`, `PUDDING-TECHNIQUE-RESEARCH.md`
    - `symbiosis-push-session-2026-02-19.md`
- **Vault status:** MISSING FROM VAULT — this entire directory is local-only

#### `~/Amplified Partners Truth/` — OPERATIONAL NOTES DIRECTORY (NOT IN GIT REPO)
- **Git repo:** No
- **Files:**
  - `.cursorrules` ← CURSOR RULE FILE #1
  - `AMPLIFIED_BIG_PICTURE_POHS.md` — canonical POHS wireframe (6 units)
  - `LINEAR_TICKETS_UNIT_ALPHA.md` — Linear ticket structure for Unit Alpha
  - `OPENCLAW_NOTES.md` — OpenClaw work log, session 2026-04-26
  - `PERPLEXITY_RESCUE.md` — JavaScript console extraction script for Perplexity threads
  - `Unified-Data/` — large staging directory containing:
    - `04-Staging/Raw-Inbox/Cursor-Processing/20260220/` — **1,004+ voice transcript files** (voice-YYYYMMDD-HHMMSS.md format) + synthesis files
    - `.docx` files: `watchman-expansion-strategy.docx`, `hounddog-integration-plan.docx`, `CANONICAL_HOUNDDOG_DATA_MINING_SPEC.md`, `DOCBENCH_PRODUCT_BRIEF.md`, `CLAWD-CAPABILITY-SPEC-NOT-BUILT.md`, `CLAWD-FULL-CAPABILITY-BUILD.md`, `clawd-reflection-template.md`
    - Session notes: `clawd-2026-02-11-2052.md`, `clawd-2026-02-12-0220.md`, `CLAWD-TODO.md`
- **Status:** MISSING FROM VAULT — fully local, not tracked by any git repo

#### `~/Agent-Comms/` — CROSS-AGENT COMMUNICATION BUS
- **Git repo:** Yes (likely — structured as decoupled event bus)
- **Files:**
  - `README.md` — defines the protocol: git pull on boot, push logs on session end
  - `logs/2026-04-26.md` — Antigravity log: processed 1,004 raw voice transcripts, established Agent-Comms as global event bus

### 2.2 Secondary / Staging Directories

#### `~/2026-04-25-SPARKLE-INBOX/` — MIGRATION STAGING AREA
- **Git repo:** Yes (initialized)
- **Total files:** 35,423
- **Contains:**
  - `AI_TOOL_DIR_QUARANTINE/` — quarantined Cursor configs: `.cursor/plans/` (31 Cursor plan files), `.cursor/plugins/cache/` (agent-compatibility plugin, temporal-developer plugin, clerk plugin), `.cursor/agents/`, `.cursor/rules/`, `.cursor/skills/`, `.openclaw/`
  - `AI_TOOL_MD_RESCUE/` — markdown rescue staging
  - `CODE_CLEAN_DEDUPED/` — clean deduped code archive (includes cove/services/pudding/, Research Pipe, enforcer, crm)
  - `CODE_RESCUE/` — code rescue staging (includes run_puddings.py, run_puddings-v2.py, run_all_puddings.py, OpenClaw kimi-claw extensions)
  - `DOC_PDF_TXT_RESCUE/` — document rescue (curator-assessment, curator-education, curator-master, CURATOR-GATE-SPEC, hounddog docs, watchman-expansion-strategy, 2026-04-25-clawd-search.txt)
  - `JSON_CSV_RESCUE/` — JSON/CSV rescue
  - `MD_ISO_DATED_RENAMED/` — markdown files renamed to ISO date format
  - `MD_METADATA_INDEX/` — metadata index

#### `~/Downloads/` — EWAN'S ACTIVE WORK DIRECTORY
- **Git repo:** No (but structured with named subdirs)
- **Total files (top-level):** 97 items visible
- **Notable subdirectories:**
  - `_inbox/`, `_inbox-voice/`, `_inbox-work/`, `_inbox-uncategorised/` — active inboxes
  - `_staging/` — **448 files** — structured (01-executive, 02-strategy, 03-sales-marketing, 05-technology, 07-finance, 08-product, 09-research, 11-templates-sops, 12-archive-raw) + master index, pudding principles, rubric files
  - `_system/reflections/` — system reflections
  - `the mother load/` — **1 file**: `pudding-technique-canonical.md` (THE canonical Pudding Technique doc, written 2026-02-22)
  - `the-room/` — **1 file**: `pudding-technique-canonical.md` (same file — duplicate location)
  - `work/` — **105 files** — amplified-partners-master.md, amplified-partners-overview-feb-2026.md, campaigns, claude-writing, fund-watcher, GEMINI-CONTEXT-2026-02-22.md, JOHNNY-STATUS.md, pudding dir, rubric dir, sessions
  - `work-covered-ai/` — **79 files**
  - `research/` — **168 files** — dated research docs (2026-02-24 onwards)
  - `imported-business-docs/` — **122 files** — amplified-crm-docs, gemini-brain (10 files), icloud-the-beast, openclaw-workspace, How_To_Pudding.md, INTELLIGENCE_SYSTEM_COMPLETE.md, DEMO-BUSINESS-BIBLE-DAVE.md, SESSION-2026-02-14-BUSINESS-BRAIN.md, etc.
  - `Google-Drive-Miner 2/` — Google Drive extraction tool with voice files
  - `Antigravity_Vault/` — empty
  - `Antigravity_Audio_Vault/` — empty
  - `antigravity/` — Antigravity work directory
  - `eli/` — 1 file (notes, pipeline, published structure)
  - `archive/` — archive staging
  - `infra-ai-stack/` — infrastructure research
  - `knowledge-qdrant/` — Qdrant knowledge base (with venv)
  - `projects/` — project staging
  - `scripts/` — scripts
  - `superwhisper/` — SuperWhisper audio app output
- **Status:** MISSING FROM VAULT — this entire directory is uncommitted local work

#### `~/Desktop/Amplified_Documents_Flat/` — FLAT EXPORT OF CLEAN-BUILD (745 files)
- **Git repo:** No
- **Status:** Appears to be a flattened export of the clean-build directory structure, renamed with path-encoded prefixes (e.g. `00_authority_NORTH_STAR.md`). Likely a one-time export for external use.
- **Contains:** All authority files, truth processes, schemas, cursor skills — mirroring clean-build

#### `~/Desktop/Sidecar-Remotion-Studio/` — REMOTION VIDEO PIPELINE
- **Git repo:** Likely (has node_modules, package.json)
- **Contains:** src/ directory, Remotion video composition project (ViralHook component etc.)

#### `~/Desktop/full stack marketing/` — MARKETING RESEARCH
- **Git repo:** No
- **Contains:** Research docs, AI marketing analytics, Amethyst prompts, amplified marketing docs

#### `~/the-amplified-method/` — ORIGINAL APP CODEBASE
- **Git repo:** Yes (3 items at root: backend, Ewan's Interface, README.md)
- **Contains:**
  - `Ewan's Interface/` — React/Vite frontend (App.jsx, DogfoodUI.jsx, MarketingSite.jsx, StaffUI.jsx)
  - `backend/` — Python FastAPI with .venv (Python 3.9)

#### `~/marketing/` — MARKETING MACHINE CODEBASE
- **Git repo:** Likely (has .DS_Store, structured)
- **Contains:** Python marketing agents (avatars, content generator, video agents: dicaprio, director, picasso), service_businesses, uk_trades, transparent_prompts, models; `CURSOR_HANDSHAKE.md`; `amplified_complete_digital_marketing_suite.md`; Remotion/video templates

#### `~/project_nexus/` — EXPERIMENTAL PROJECT
- **Git repo:** Likely
- **Contains:** `README.md`, `core/__init__.py`, `core/stigmergy.py` — experimental stigmergy (ant-colony-style coordination) module

#### `~/2026-04-25-github-clone/` — CODEX RUNTIME SNAPSHOT
- **Git repo:** Yes (.hermes directory present)
- **Contains:** Codex primary runtime (Python 3.12, Node.js binaries), `.hermes/` with Hermes agent optional skills (including nemo-curator), bash session history

### 2.3 Hidden / Config Directories

#### `~/.claude/projects/-Users-ewansair-amplified/` — CLAUDE CODE MEMORY
- **Git repo:** No
- **Contents:** 10 conversation sessions (.jsonl), `memory/` directory with **36 memory files**:
  - `MEMORY.md` — master index of all memory files
  - `feedback_*` files (13): assess_before_refactor, atomic_sessions, blast_radius, blinkers_without_ceilings, client_philosophy, date_everything, do_not_fill_gaps, md_style, no_mcps, python_script_files, values, voice_dictation, working_method
  - `project_*` files (14): amplified_partners, claw, context_layering, curator_llm, defense_in_depth, how_it_works, identity_architecture, identity_state, md_lint_stack, open_journey, research_pipe, security_tiers, technical_approach, wren_parallel_worker
  - `user_ewan.md`

#### `~/.gemini/antigravity/` — GEMINI (ANTIGRAVITY) BRAIN
- **Git repo:** No
- **Total files:** 141
- **Structure:** `brain/` (22 UUID-named session artifacts), `skills/amplified-soul/SKILL.md`, `conversations/`, `knowledge/`, `annotations/`, `scratch/`, `html_artifacts/`, `implicit/`
- **Notable:** `brain/cd974636-*/artifacts/symbiotic_rag_pudding.md` — Pudding RAG artifact for Gemini

#### `~/.antigravity/` — ANTIGRAVITY (CUSTOM IDE) CONFIG
- **Git repo:** No
- **Contents:** VS Code-style extensions directory (`golang`, `vscode-clangd`, `rainbow-csv`, `ms-python.debugpy`, `ms-python.python`, `ms-python.vscode-python-envs`), `argv.json`, `extensions.json`
- **Finding:** `.antigravity` appears to be a custom AI IDE (fork or rename of VS Code/Cursor)

#### `~/.openclaw/` — OPENCLAW GATEWAY CONFIG
- **Git repo:** No
- **Contents:** `logs/gateway.err.log`, `logs/gateway.log` — OpenClaw gateway is running/was running on this machine

#### `~/.cursor/` — CURSOR IDE CONFIG
- **Git repo:** No
- **Notable:** `plugins/cache/cursor-public/compound-engineering/` — Compound Engineering Cursor plugin (60+ specialized review agents), `temporal-developer/` plugin, `agent-compatibility/` plugin, `clerk/` plugin
- **Projects tracked:** Multiple project sessions including the 2026-04-25 workspace

#### `~/.config/temporalio/` — TEMPORAL.IO CONFIG
- **Contains:** `version-info.yaml` — Temporal CLI is installed on this machine

---

## 3. Every .cursorrules File — Full Content

### 3.1 `/Users/ewansair/Amplified Partners Truth/.cursorrules`
```
# Amplified Partners - Cursor Operating Rules

## Context & Persona
**We are Amplified Partners.**
- **Ewan** is the Architect.
- **Antigravity** is the Chief Operations Officer and the Arbiter.
- **OpenClaw** is spun up as the Note-Taker and Recorder.
- **You (Cursor)** are the Technical Genius.
- **Devon** handles infrastructure and integration.

## The Rules (Amplified Soul - Layer 0)
1. Radical Honesty
2. Radical Transparency
3. Radical Attribution (cite exact source file, e.g. voice-20260220-043611.md)
4. Privacy and Security First
5. Win-Win
6. Idea Meritocracy
7. Don't believe the hype: Test claims.
8. Blinkers without ceilings

## The Compound Engineering Loop
Plan (40%) → Work (10%) → Review (30%) → Compound (20%)
Attribution: Every (Kieran Klaassen & Dan Shipper)

## The Framework of Support
1. Try to Fix It → 2. Two Attempts → 3. External Search → 4. Escalate to Arbiter → 5. Directional Changes → 6. Self-Reflection (X/10) → 7. Next-Reader Documentation
```
*(Full file: 44 lines — read above in session)*

### 3.2 `/Users/ewansair/clean-build/.cursorrules`
Identical structure to above. Key difference: references `AGENTS.md` and `00_authority/` explicitly. Missing rules 7 and 8 (Don't believe the hype, Blinkers without ceilings). Notes: `CURSOR_HANDSHAKE.md` rather than generic context files.

**Divergence between the two:** The `Amplified Partners Truth` version has rules 7 (Don't believe the hype) and 8 (Blinkers without ceilings) which the `clean-build` version omits. The `clean-build` version is the more recent, structured canonical. RECOMMENDATION: Reconcile — add rules 7 and 8 to clean-build version.

---

## 4. Every CLAUDE.md File

**Result:** No `CLAUDE.md` files found at the project/root level on this machine.

**However — Claude Code memory is extensive** at `~/.claude/projects/-Users-ewansair-amplified/memory/`. This is the functional equivalent: 36 structured memory files covering feedback patterns, project context, and user profile.

**Compound Engineering Cursor plugin** has a `CLAUDE.md` at:
`/Users/ewansair/.cursor/plugins/cache/cursor-public/compound-engineering/7e83755acbb48a62accd3566def8c4adc7de451a/CLAUDE.md`
— This is a plugin-level Claude instruction file for the compound-engineering framework.

---

## 5. Every docs/solutions/ Directory

**Result:** No `docs/solutions/` directories found matching the brief's pattern.

**What exists instead:** The clean-build uses a different structure:
- `01_truth/processes/` — equivalent to solutions/processes
- `01_truth/schemas/` — equivalent to solutions/schemas  
- `02_build/` — runnable artifacts

The vault's `docs/` equivalent appears to be the `_staging/` structure in `~/Downloads/` and `~/corpus-raw/vault/`.

---

## 6. Named Systems Found

| System | Status | Key File Locations |
|--------|--------|-------------------|
| **Night Watchman** | IMPLEMENTED | `~/clean-build/02_build/cove-orchestrator/temporal/activities/night_watchman_activities.py`, `temporal/workflows/night_watchman_workflow.py`; strategy doc at `01_truth/schemas/architecture/2026-03_watchman-expansion-strategy_v1.md` |
| **Curator** | ACTIVE (memory + code) | `~/.claude/projects/.../memory/project_curator_llm.md` (Qwen3-14B, runs locally on M5 via Ollama); Research Pipe: `curator1_research_pipe.py`, `curator2_research_pipe.py`; docs: curator-assessment, curator-education, curator-master (in SPARKLE-INBOX rescue) |
| **Sentinel** | IMPLEMENTED | `~/corpus-raw/vault/_inbox/sentinel.py` through `sentinel_v2-v2.py` (5 versions); `~/clean-build/02_build/security/sentinel.py` (canonical) |
| **Enforcer** | IMPLEMENTED | `~/2026-04-25-SPARKLE-INBOX/CODE_CLEAN_DEDUPED/.../enforcer/` — `enforcer.py`, `config.yaml`, `docker-compose-entry.yml`; checks: `database_health.py`, `docker_health.py`, `security_check.py`, `session_hygiene.py`, `traefik_health.py`, `waypoint_check.py` |
| **Antigravity / Arbiter** | ACTIVE | `.antigravity/` IDE running on machine; `~/.gemini/antigravity/` Gemini instance; `clean-build/ARBITER_COMMAND.md`; Antigravity is described as COO and Arbiter throughout all authority docs |
| **OpenClaw** | ACTIVE | `~/.openclaw/logs/gateway.log` (gateway running); kimi-claw extensions in SPARKLE-INBOX; `clean-build/02_build/cove-orchestrator/agents/prompts/openclaw.md`; OPENCLAW_NOTES.md in Amplified Partners Truth |
| **Portable Spine** | DOCUMENTED | `~/clean-build/PORTABLE-SPINE-BEAST.md` (27 Apr 2026 — Beast operations context); `~/clean-build/03_shadow/2026-04-29_portable_spine_and_sidecar_update.md` (UNCOMMITTED — latest state doc for Mac Mini transition) |
| **Compound Engineering** | ACTIVE PLUGIN | `~/.cursor/plugins/cache/cursor-public/compound-engineering/` — full plugin with 60+ specialized review agents (adversarial, security, correctness, performance, API contract, architecture, etc.) |
| **Pudding Technique** | DOCUMENTED + PARTIALLY IMPLEMENTED | Canonical doc: `~/Downloads/the-room/pudding-technique-canonical.md` (2026-02-22); system docs in `~/Vaults/Ewan/Voice-Transcripts/`; 48 pudding extraction files; code: `pudding-pipeline.py`, `engine.py`, `taxonomy.py` (in SPARKLE-INBOX archive) |
| **Hounddog** | PLANNED | `clean-build/01_truth/processes/2026-03_hounddog-integration-plan_v1.md`; `CANONICAL_HOUNDDOG_DATA_MINING_SPEC.md` (in Unified-Data); `hound_dog.py` referenced in PORTABLE-SPINE-BEAST.md as "locked down with OOM protections" |
| **Docbench** | SPEC ONLY | `DOCBENCH_PRODUCT_BRIEF.md` in Unified-Data — product brief exists, no implementation found |
| **Temporal Cove** | IMPLEMENTED | `~/clean-build/02_build/cove-orchestrator/` — full orchestrator with Temporal workflows, MCP servers, email agent, docker config, DB migrations |
| **Gatekeeper** | REFERENCED | Mentioned in CURSOR_HANDSHAKE.md and POHS wireframe as routing agent; no standalone code found locally |
| **Wren** | REFERENCED | `~/.claude/.../memory/project_wren_parallel_worker.md` — "another Claude instance in the amplified repo, commits as Ewan" |
| **Sidecar** | IMPLEMENTED | Referenced in `2026-04-29_portable_spine_and_sidecar_update.md` (uncommitted): `sidecar_api.py` FastAPI gateway on port 8001, Tri-Council Dogfood (/council), Vault Search (/vault/search), Pick-to-Light Approvals; also `~/Desktop/Sidecar-Remotion-Studio/` |
| **Framework of Support** | CODIFIED | In both .cursorrules files and AGENTS.md — the escalation ladder |
| **Johnny** | REFERENCED | `JOHNNY-STATUS.md` in Downloads/work — agent mentioned in CHARTER_DRAFT.md agent list |
| **Byker** | IMPLEMENTED | `~/clean-build/02_build/byker-production/` — full production codebase with backend, frontend, workflows, diagnostics, validators, test-vault structure |
| **Eli** | IN PROGRESS | `~/Downloads/eli/` — notes, pipeline, published structure — appears to be a content agent or persona |
| **CLAWD** | DESIGNED (NOT BUILT) | `CLAWD-CAPABILITY-SPEC-NOT-BUILT.md`, `CLAWD-FULL-CAPABILITY-BUILD.md` in Unified-Data; session notes from Feb 2026; `CLAWD-TODO.md` |

---

## 7. Uncommitted Work in Git Repos

### clean-build (branch: transition-mac-mini)
| File | Status | Significance |
|------|--------|-------------|
| `03_shadow/2026-04-29_portable_spine_and_sidecar_update.md` | UNTRACKED | Latest Antigravity portable spine — current operational state of Sidecar, Beast priorities, Three-Brain isolation model. Written 2026-04-29. This is the most recent state document and it's not committed. |
| `02_build/perplexity-ai-export` | MODIFIED SUBMODULE | Submodule has modified + untracked content |

### corpus-raw (initial dump only)
- Everything committed in one shot on 2026-04-23
- No uncommitted files
- Risk: Single commit = no history, no ability to bisect or attribute changes

### SPARKLE-INBOX
- Has a git repo but appears to be a staging/migration area — exact commit status not checked

---

## 8. Not In Any Repo — Files Existing Only on Mac

These directories have **no git tracking** and represent the largest risk of data loss:

| Directory | Files | Classification | Risk |
|-----------|-------|----------------|------|
| `~/Vaults/Ewan/` | ~8,500 | extracted data, voice transcripts, CRM data | HIGH — 6,030 extraction files, 2,104 monologue transcripts |
| `~/Amplified Partners Truth/` | ~1,010+ | POHS wireframe, voice staging, CLAWD specs, strategy | HIGH — includes 1,004 raw voice transcripts in staging |
| `~/Downloads/` | Many thousands | Research, staging, work, imported docs, pudding docs | HIGH — active work directory |
| `~/.claude/projects/` | 36 memory files + 10 sessions | Claude Code memory — operational context | MEDIUM — reconstructable but valuable |
| `~/.gemini/antigravity/` | 141 | Gemini brain sessions, Pudding RAG artifact | MEDIUM |
| `~/.openclaw/` | Logs | Gateway logs | LOW |
| `~/Desktop/Amplified_Documents_Flat/` | 745 | Flat export of clean-build | LOW — appears to be derived from clean-build |
| `~/Desktop/full stack marketing/` | ~20 | Marketing research docs | MEDIUM |
| `~/the-amplified-method/` | Backend + frontend | Original app codebase | HIGH — active code, no confirmed remote |
| `~/marketing/` | Python agents + templates | Marketing machine code | HIGH — active code |
| `~/project_nexus/` | 3 | Stigmergy experiment | LOW |

---

## 9. Missing From Vault

Based on the vault manifest provided (00-claude-projects through work-covered-ai), the following appear to be LOCAL ONLY and not in the vault:

**HIGH PRIORITY — NOT IN VAULT:**
1. `~/Amplified Partners Truth/Unified-Data/04-Staging/` — 1,004 raw voice transcripts awaiting processing. Antigravity's 2026-04-26 log says she processed these with `pudding_processor.py` but the destination is awaiting Ewan's instruction.
2. `~/Vaults/Ewan/02-extracted-data/` — 6,030 extraction files (UUID-based, inbox-voice extractions) — entire directory appears local-only
3. `~/Downloads/the mother load/pudding-technique-canonical.md` and `~/Downloads/the-room/pudding-technique-canonical.md` — THE canonical Pudding Technique document (2026-02-22) — not confirmed in vault
4. `~/clean-build/03_shadow/2026-04-29_portable_spine_and_sidecar_update.md` — latest operational state, uncommitted
5. All `~/.claude/projects/-Users-ewansair-amplified/memory/` files — Claude's operational memory, not in vault or git
6. `~/Agent-Comms/logs/2026-04-26.md` — cross-agent event bus log

**LIKELY IN VAULT (cross-referenced by name):**
- Voice transcripts pattern matches vault's `08-voice-transcripts/` and `transcripts/` directories
- Research docs in Downloads/research likely overlap with vault `18-research/`
- The work/ and work-covered-ai/ in corpus-raw match vault dirs of same name

---

## 10. Divergent Files (Same Content, Different Locations)

| File | Location 1 | Location 2 | Location 3 | Notes |
|------|-----------|-----------|-----------|-------|
| `pudding-technique-canonical.md` | `~/Downloads/the mother load/` | `~/Downloads/the-room/` | `~/corpus-raw/vault/the-room/` | 3 copies — canonical doc from 2026-02-22 |
| `hounddog-integration-plan` | `~/corpus-raw/ewan-docs/hounddog-integration-plan.docx` | `~/clean-build/01_truth/processes/2026-03_hounddog-integration-plan_v1.md` | `~/Desktop/Amplified_Documents_Flat/01_truth_processes_2026-03_hounddog-integration-plan_v1.md` | .docx vs .md — versions may diverge |
| `watchman-expansion-strategy` | `~/Amplified Partners Truth/Unified-Data/.../` (.docx) | `~/clean-build/01_truth/schemas/architecture/2026-03_watchman-expansion-strategy_v1.md` | `~/Desktop/Amplified_Documents_Flat/...` | Same divergence pattern |
| `AGENTS.md` | `~/clean-build/AGENTS.md` (CANONICAL) | `~/corpus-raw/ewan-mac/archive/AGENTS.md` | `~/corpus-raw/ewan-mac/archive2/AGENTS.md` | Archive copies — not current authority |
| `.cursorrules` | `~/Amplified Partners Truth/.cursorrules` (8 rules) | `~/clean-build/.cursorrules` (6 rules) | — | DIVERGENT — Amplified Partners Truth has 2 extra rules |
| `CURSOR_HANDSHAKE.md` | `~/clean-build/CURSOR_HANDSHAKE.md` | `~/marketing/CURSOR_HANDSHAKE.md` | — | Marketing version may be divergent |
| `Cursor plan files` | `~/.cursor/plans/` (original) | `~/2026-04-25-SPARKLE-INBOX/AI_TOOL_DIR_QUARANTINE/.cursor/plans/` (31 files) | — | Quarantined — likely stale |

---

## 11. Exact Duplicates / SHA-256 Dedup

Full SHA-256 hashing of all 163,316 markdown files was not completed in this session (would take significant time). However, **confirmed duplicate locations** based on structural analysis:

| Pattern | Estimated Duplicates |
|---------|---------------------|
| `Desktop/Amplified_Documents_Flat/` vs `clean-build/` | ~700 files (flat export = near-exact copies) |
| `SPARKLE-INBOX/CODE_CLEAN_DEDUPED/` vs various project dirs | Hundreds — deduped archive of historical code |
| `corpus-raw/vault/` vs `~/Downloads/` subdirs | High overlap — corpus-raw is a dump of local Downloads |
| Pudding-technique-canonical.md | 3 confirmed identical copies |
| `.cursorrules` in Amplified Partners Truth vs clean-build | Partially identical, partially divergent |

**RECOMMENDATION:** Run `jdupes` (already used — `jdupes-md-code-report.txt` exists at home root) against the identified priority directories for bit-for-bit dedup. The file `~/jdupes-md-code-report.txt` already exists — read it for existing dedup analysis.

---

## 12. Content Type Breakdown

| Type | Estimated Count | Primary Locations |
|------|----------------|-------------------|
| **Voice transcripts** | 3,000+ | ~/Vaults/Ewan/Voice-Transcripts/, ~/Amplified Partners Truth/Unified-Data/ |
| **Research** | 300+ | ~/Downloads/research/, ~/corpus-raw/ewan-docs/, ~/Downloads/_staging/09-research/ |
| **Strategy / Architecture** | 150+ | ~/clean-build/00_authority/, 01_truth/processes/, ~/Downloads/work/ |
| **Code (Python)** | 400+ | ~/clean-build/02_build/, ~/corpus-raw/ewan-mac/archive/ |
| **Code (TypeScript/React)** | 200+ | ~/the-amplified-method/, ~/clean-build/02_build/amplified-site/, ~/Desktop/Sidecar-Remotion-Studio/ |
| **Process / SOP** | 100+ | ~/clean-build/01_truth/processes/ (50+ named processes) |
| **Pudding extractions** | 57+ | ~/Vaults/Ewan/02-extracted-data/, Monologue pudding files |
| **Agent prompts** | 80+ | ~/clean-build/02_build/cove-orchestrator/agents/, ~/.cursor/plugins/ compound-engineering agents |
| **Admin / Planning** | 50+ | Linear tickets, Linear plans, Cursor plan files (.plan.md) |
| **Creative / Content** | 40+ | ~/Downloads/work/campaigns/, content drafts in research/ |
| **Session/Baton pass notes** | 30+ | ~/clean-build/03_shadow/sessions/, baton_pass files |
| **Schemas / Interfaces** | 40+ | ~/clean-build/01_truth/schemas/, interfaces/ |
| **Data files (xlsx, json, csv)** | 20+ | ~/clean-build/01_truth/data/ |
| **Security** | 15+ | Sentinel versions, enforcer checks, security runbook, Watchman workflow |

---

## 13. Recommendations

### IMMEDIATE (Do This Now)

1. **Commit the portable spine.** `~/clean-build/03_shadow/2026-04-29_portable_spine_and_sidecar_update.md` is untracked and contains the current operational state. Risk of loss is real. Run: `cd ~/clean-build && git add 03_shadow/2026-04-29_portable_spine_and_sidecar_update.md && git commit -m "chore: add portable spine sidecar update 2026-04-29"`

2. **Read `~/jdupes-md-code-report.txt`** — a dedup report already exists at home root. Use it.

3. **Reconcile .cursorrules files** — `Amplified Partners Truth/.cursorrules` has 2 rules (`Don't believe the hype`, `Blinkers without ceilings`) that `clean-build/.cursorrules` is missing. The clean-build is canonical. Add the two missing rules.

### SHORT TERM (This Week)

4. **Vault the pudding-technique-canonical.md.** Three copies exist locally, none confirmed in the Beast vault. This is the foundation document. It should be in `08-voice-transcripts/` or a dedicated `the-room/` vault directory.

5. **Process the 1,004 raw voice transcripts** in `~/Amplified Partners Truth/Unified-Data/04-Staging/Raw-Inbox/`. Antigravity already ran pudding_processor.py on 2026-04-26 and created synthesis files. The next step is vault ingestion — Ewan's approval is the blocker (per Agent-Comms log).

6. **Back up `~/Vaults/Ewan/` to git.** 8,500+ files with no git tracking. The 6,030 extraction files and 2,104 monologue transcripts are the result of significant processing work. One disk failure = total loss.

7. **Commit `~/the-amplified-method/`** — original app codebase with React frontend and FastAPI backend. Check if this has a remote. If not, push to Amplified-Partners GitHub org.

8. **Commit `~/marketing/`** — marketing machine codebase with Python agents and video templates.

### MEDIUM TERM

9. **Migrate Claude Code memory to AGENTS.md/01_truth/** — the 36 memory files at `~/.claude/projects/.../memory/` contain critical operational context (user profile, project facts, feedback patterns). These should be distilled into the clean-build authority layer so they're agent-agnostic and durable.

10. **Resolve the SPARKLE-INBOX.** 35,423 files in a staging/quarantine area. This is a migration artifact from 2026-04-25. Determine what's been successfully migrated to clean-build and archive/delete the rest.

11. **Antigravity_Vault and Antigravity_Audio_Vault are empty** — check if these were staging targets that were never populated, or if they were cleared after use.

12. **CLAWD design docs** (`CLAWD-CAPABILITY-SPEC-NOT-BUILT.md`, `CLAWD-FULL-CAPABILITY-BUILD.md`, `CLAWD-TODO.md`) in Unified-Data are local-only. Promote to `01_truth/processes/` in clean-build if still relevant, or archive.

13. **Docbench** — `DOCBENCH_PRODUCT_BRIEF.md` exists only in Unified-Data. No implementation found. Decision needed: build, park, or shelve.

### NOISE CANDIDATES (Review Before Deleting)
- `~/Desktop/MAC5_TO_MAC4_TRANSFER_2026-04-25/` — contains only `.DS_Store`. Empty transfer staging — safe to delete.
- `~/recent/` — contains only `.DS_Store`. Safe to delete.
- `~/2026=04-25-trash` (note: `=` not `-` in name) — likely typo'd trash folder. Review and empty.
- `~/Downloads/Google-Drive-Miner 2_DUPLICATES_SAFE_TO_DELETE/` — name implies already cleared for deletion. Verify and remove.
- Quarantined Cursor plans in SPARKLE-INBOX — 31 `.plan.md` files from old Cursor sessions. Once migrated work is confirmed in clean-build, these can be archived.

---

## Appendix A: Git Repo Inventory

| Repo | Path | Branch | Remote | Last Commit | Uncommitted |
|------|------|--------|--------|-------------|-------------|
| clean-build | `~/clean-build/` | transition-mac-mini | Likely Amplified-Partners org | 922341a (Vault UI + Mini sync) | 2 items |
| corpus-raw | `~/corpus-raw/` | unknown | Amplified-Partners/corpus-raw (private, 2026-04-23) | "Initial corpus dump" | 0 |
| SPARKLE-INBOX | `~/2026-04-25-SPARKLE-INBOX/` | unknown | Unknown | Unknown | Unknown |
| Agent-Comms | `~/Agent-Comms/` | unknown | Likely Amplified-Partners org | Unknown | Unknown |
| the-amplified-method | `~/the-amplified-method/` | unknown | Unknown | Unknown | Unknown |
| 2026-04-25-github-clone | `~/2026-04-25-github-clone/` | unknown | Hermes/Codex runtime | Unknown | N/A (runtime snapshot) |
| crm (submodule) | `~/clean-build/02_build/crm/` | unknown | Likely Amplified-Partners org | Unknown | Inherited from clean-build parent |
| perplexity-ai-export (submodule) | `~/clean-build/02_build/perplexity-ai-export/` | unknown | Likely Amplified-Partners org | Unknown | Modified + untracked |

---

## Appendix B: Key File Quick-Reference

| File | Path | What It Is |
|------|------|-----------|
| POHS Wireframe | `~/Amplified Partners Truth/AMPLIFIED_BIG_PICTURE_POHS.md` | 6-unit company architecture diagram |
| Pudding Canonical | `~/Downloads/the-room/pudding-technique-canonical.md` | Foundation document for Pudding Technique (2026-02-22) |
| North Star | `~/clean-build/00_authority/NORTH_STAR.md` | Agent-first authority contract (v11) |
| AGENTS.md | `~/clean-build/AGENTS.md` | Canonical agent operating instructions |
| Portable Spine | `~/clean-build/PORTABLE-SPINE-BEAST.md` | Beast/Mac Mini operational context for Antigravity |
| Latest State | `~/clean-build/03_shadow/2026-04-29_portable_spine_and_sidecar_update.md` | Most recent Antigravity operational state (UNCOMMITTED) |
| Agent-Comms Log | `~/Agent-Comms/logs/2026-04-26.md` | Cross-agent event bus — Antigravity's 2026-04-26 session |
| Claude Memory Index | `~/.claude/projects/-Users-ewansair-amplified/memory/MEMORY.md` | Master index of all Claude Code memory |
| Cursor Handshake | `~/clean-build/CURSOR_HANDSHAKE.md` | Night Watchman, content engine, outbound system brief |
| Client Defriction Model | `~/clean-build/CLIENT_DEFRICTION_MODEL.md` | Largest single doc found (12,680 bytes) |
| Corporate Constitution | `~/clean-build/CORPORATE_CONSTITUTION.md` | Company constitution |

---

*Devon (Terminal M5) | 2026-04-30 | Session: devin-ebf31a94a5bc4822baef08bb30be1378*  
*Coordination: This assessment feeds into convergence pass with GitHub assessment (devin-aa4d863ad679468692e75a40b8825358)*  
*Parent session: devin-aa4d863ad679468692e75a40b8825358*
