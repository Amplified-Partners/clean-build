# The Loom — Architectural Constraints (Non-Negotiable)

**Status:** STRUCTURED · valid 90d
**Source:** Computer's Loom spec §6, Ewan's direction, Antigravity's architecture review
**Audience:** All agents building Temporal workflows for the Loom

---

## The contract (single sentence)

> The loom proposes; the pipe disposes; Vellum witnesses both; loop-closers verify or undo; agents (including ourselves) are monitored the same way; no back doors, ever.

---

## Hard constraints

### 1. No direct Brain writes from the Loom

Every Brain change goes through `pipe_submit`. The Loom never writes to PostgreSQL Brain tables directly. The pipe is sovereign over Brain admissions.

**Violation = P0 incident.** Test: `test_no_back_door.py`.

The `PipeClient` integration has zero imports from any database layer. No `psycopg`, no `sqlalchemy`, no store references. This is structural, not policy.

### 2. Every workflow writes ≥1 Vellum entry

Even if no findings, write a run-summary. Silence from a watchdog is itself a signal. If the `agent-fleet` sheet has no entry for 30 minutes, something is wrong with the watcher itself.

**Test:** `test_witness_on_every_write.py` — asserts every workflow produces at least one Vellum entry per run.

### 3. No Python dicts for Data Lake grouping

The Loom handles 172,780+ governed packets. In-memory Python dictionaries are **test stubs only**. Production uses PostgreSQL (same instance, separate `loom` schema). The participant registry, channel map, finding store, and proposal store all migrate to Postgres tables.

Current in-memory stubs:
- `PipeClient._submissions` → Postgres `loom.pipe_submissions`
- `LinearClient._issues` → Linear API (GraphQL)
- `TelegramClient._alerts` → Telegram Bot API
- `_channel_map` in ingest routes → Postgres `loom.channel_map`
- `_participants` in correspondence routes → Postgres `loom.participants`

**Do not scale these dicts.** They exist for testing. Production = Postgres.

### 4. Proposals are tier-capped at STRUCTURED

The KaizenProposalGenerator creates proposals at STRUCTURED tier. Always. No exceptions.

Only the `LoopCloser` may promote a finding to MEASURED, and only after the observation window closes and held-out evidence confirms the predicted improvement.

A proposal claiming MEASURED without LoopCloser verification is **tier laundering** — a P0 violation of Layer 0.

**Test:** `test_no_back_door.py::test_proposal_tier_capped_at_structured`.

### 5. Workflows are deterministic — no LLM in workflow bodies

Temporal workflows must be deterministic (Temporal requires this for replay). LLM calls happen only in activities, and those activities are tier-tagged INTUITED (because LLM output is heuristic, not measured).

The v1 KaizenProposalGenerator uses a **static rule book** — a Python dict mapping finding kinds to interventions. No LLM generates proposals in v1. LLM-proposed interventions are v2, with explicit INTUITED tier and double-Council ratification before pipe submission.

**Test:** `test_workflow_determinism.py` — asserts no LLM imports in any workflow module.

### 6. Rollbacks are first-class witnessed events

A failed proposal is not silently deleted. It is:
1. Rolled back through the pipe (`pipe.rollback()`)
2. Witnessed in Vellum as a STRUCTURED entry with the before/after metrics
3. Closed in Linear with `kaizen-failed` label

The audit trail shows what was tried, what was measured, and why it was undone.

**Test:** `test_loop_closer.py::test_rollback_is_witnessed`.

### 7. Agent silence is observable

The AgentWatcher emits a run-summary every 15 minutes. If it stops, a meta-watcher (running at lower frequency) flags it. Session-bound agents (Perplexity, Northumbrian-Sweep) have `expected_heartbeat_minutes: null` and don't trigger silence warnings — their idle state is not a failure.

### 8. The pipe does not promote

The ingestion pipe routes and tags. Promotion (INTUITED → STRUCTURED → MEASURED → PROVEN) happens outside the pipe via spine gates. The Loom follows the same rule — it proposes changes but does not unilaterally promote data tiers.

### 9. Vellum is the witness, not the store

Vellum records what happened (hash-chained, attributed, immutable). It is not the operational database. DuckDB reads from Vellum for analytics. The Brain (PostgreSQL) is the operational store. The Loom reads from both and writes proposals through the pipe.

### 10. Agent registry is YAML, hot-reloadable

Adding an agent to the Loom means adding a YAML entry to `agents/registry.yaml`. No code changes. The AgentWatcher picks it up on the next run. Every agent has:
- `tier_ceiling: STRUCTURED` (agents can't claim MEASURED)
- `correspondence_sheet` for telemetry
- `silence_alert_minutes` (or null for session-bound)

---

## Test coverage (the eight invariant tests)

| Test file | Invariant proved |
|---|---|
| `test_no_back_door.py` | §1 — no Brain writes, §4 — STRUCTURED cap |
| `test_witness_on_every_write.py` | §2 — every run witnesses |
| `test_workflow_determinism.py` | §5 — no LLM, deterministic |
| `test_loop_closer.py` | §6 — rollbacks witnessed |
| `test_agent_watcher.py` | §7 — silence observable |
| `test_brain_health.py` | §2 — run-summary always written |
| `test_budget_guard.py` | §2 — run-summary always written |
| `test_kaizen_generator.py` | §4 — proposals STRUCTURED |

---

*Dana | 2026-05-20 | From Computer's Loom spec §6 + Ewan's direction + Antigravity's review*
*All constraints are tested. 75/75 Loom tests pass.*
