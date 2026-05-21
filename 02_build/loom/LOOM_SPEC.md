# The Loom — Spec for Devin (and All Agents)

**To:** Devin (with help from Northumbrian-Sweep, Antigravity, any engineer agent)
**From:** Computer (Perplexity session, 2026-05-20, ~21:40 BST)
**For:** Ewan Bramley (Amplified Partners)
**Subject:** Minimum-viable orchestration layer that links Vellum + Brain + DuckDB + the pipe + Linear, health-checks itself, monitors every agent (Devin / Antigravity / Perplexity / Cove / others), and produces witnessed Kaizen outcomes automatically
**Tier:** STRUCTURED (architectural design; calibrate after first deploy)
**Status:** spec for build; small, focused, composable

---

## 0. Why this exists

We have the parts:

- **Vellum 0.2.0** — witness, hash-chained, Correspondence mode for human↔agent and agent↔agent
- **Postgres + pgvector** — the Brain
- **The ingestion pipe** — Python, sovereign over Brain admissions
- **DuckDB + `dq` CLI** — read-side analytics (scaffolding underway in Antigravity)
- **Temporal on Beast** — workflow runtime, already running for Cove
- **Linear** — work queue
- **Mission Control** — governance UI (to be restored)

What we don't have yet is the **continuous orchestration** that ties them into a living Kaizen loop. The loom is that.

This spec is the **smallest version that proves the pattern**, plus the agent-self-monitoring Ewan asked for explicitly. ~700 lines of Python total. Buildable in a focused day.

---

## 1. Architectural principle

> The loom proposes. The pipe disposes. Vellum witnesses both. Loop-closers verify or roll back. No back doors.

Three workflow categories:

1. **Health checks** — read state, compare to baselines, write findings
2. **Outcome producers** — read findings, propose interventions, submit to pipe, open Linear issues
3. **Loop-closers** — verify proposed changes actually worked, roll back if not

Plus a fourth that Ewan requested explicitly:

4. **Agent watchers** — monitor every agent (Devin, Antigravity, Perplexity, Cove, others), emit their telemetry into Vellum, detect when an agent is drifting, failing, or going quiet

Every workflow follows the same shape. Same reads, same writes, same witness, same gate.

---

## 2. The minimum viable build — five workflows, five integrations

### 2.1 The five workflows to ship first

| Workflow | Category | Schedule | What it does |
|---|---|---|---|
| `BrainHealthCheck` | health | nightly 03:30 | Reads DuckDB metrics, writes findings to `brain-health` sheet |
| `AgentWatcher` | agent | every 15 min | Polls each registered agent, writes telemetry to `agent-fleet` sheet, alerts on silence/drift |
| `KaizenProposalGenerator` | outcome | nightly 06:00 | Reads 24h of findings, generates pipe submissions and Linear issues |
| `LoopCloser` | loop-closer | event-driven | Per proposal, waits the observation window, validates or rolls back |
| `BudgetGuard` | health | hourly | Sums vendor spend across DeepSeek / OpenAI / Kimi / Grok / Anthropic; alerts pre-cap |

### 2.2 The five integrations they share

| Integration | Where it lives | What it does |
|---|---|---|
| `vellum_client` | `loom/integrations/vellum.py` | Read sheets, write entries, all via Vellum's REST API with auth |
| `dq_client` | `loom/integrations/dq.py` | Run named DuckDB queries from the manifest |
| `pipe_client` | `loom/integrations/pipe.py` | Submit candidates / proposals; subscribe to outcomes |
| `linear_client` | `loom/integrations/linear.py` | Create issues, label, transition state |
| `telegram_client` | `loom/integrations/telegram.py` | Critical alerts only — never warnings |

That's the whole spec at a glance. The rest of this document is the detail.

---

## 3. Repository layout

```
amplified-loom/
├── pyproject.toml
├── README.md
├── loom/
│   ├── __init__.py
│   ├── worker.py                    # Temporal worker entrypoint
│   ├── config.py                    # env vars, defaults, agent registry
│   ├── findings.py                  # Finding dataclass + serialisation
│   ├── proposals.py                 # Proposal dataclass + tier rules
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── brain_health.py
│   │   ├── agent_watcher.py
│   │   ├── kaizen_generator.py
│   │   ├── loop_closer.py
│   │   └── budget_guard.py
│   ├── activities/
│   │   ├── __init__.py
│   │   ├── read_metrics.py
│   │   ├── write_outcomes.py
│   │   └── verify_proposals.py
│   └── integrations/
│       ├── __init__.py
│       ├── vellum.py
│       ├── dq.py
│       ├── pipe.py
│       ├── linear.py
│       └── telegram.py
├── agents/                          # registry of agents to monitor
│   └── registry.yaml
├── tests/
│   ├── test_brain_health.py
│   ├── test_agent_watcher.py
│   ├── test_kaizen_generator.py
│   ├── test_loop_closer.py
│   ├── test_budget_guard.py
│   ├── test_no_back_door.py         # asserts loom never writes Brain directly
│   └── test_witness_on_every_write.py
└── ops/
    ├── docker-compose.yml           # local dev
    ├── beast.systemd.service        # production unit
    └── runbook.md                   # 3am operator notes
```

---

## 4. Shared types

### 4.1 `Finding`

Every health-check produces zero or more findings. The dataclass:

```python
# loom/findings.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

Severity = Literal["info", "warning", "critical"]

@dataclass
class Finding:
    id: str = field(default_factory=lambda: str(uuid4()))
    kind: str = ""                          # e.g. "triangulation_drop"
    severity: Severity = "info"
    source_workflow: str = ""               # who found this
    evidence: dict = field(default_factory=dict)
    discovered_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))
    tier: str = "STRUCTURED"                # always; findings are heuristic
    related_entity_ids: list[str] = field(default_factory=list)

    def to_vellum_entry(self) -> dict:
        return {
            "entry_type": "metric",
            "author": self.source_workflow,
            "content": f"{self.kind} ({self.severity})",
            "epistemic_status": "STRUCTURED",
            "metadata": {
                "finding_id": self.id,
                "evidence": self.evidence,
                "related": self.related_entity_ids,
            },
        }
```

### 4.2 `Proposal`

Every outcome the loom wants to enact is a proposal, submitted through the pipe:

```python
# loom/proposals.py
@dataclass
class Proposal:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    rationale: str = ""
    evidence_finding_ids: list[str] = field(default_factory=list)
    intervention: dict = field(default_factory=dict)   # what to actually do
    reversible: bool = True
    observation_window_hours: int = 168                # default 7 days
    expected_metric: str = ""                          # named DuckDB query
    expected_delta: dict = field(default_factory=dict) # baseline vs target
    tier: str = "STRUCTURED"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_pipe_submission(self) -> dict:
        return {
            "kind": "meta_change",
            "payload": self.intervention,
            "attributed_to": "loom.kaizen_generator",
            "tier": self.tier,
            "evidence_refs": self.evidence_finding_ids,
            "rollback_plan": {
                "reversible": self.reversible,
                "window_hours": self.observation_window_hours,
            },
        }
```

**Discipline note:** proposals are tier-capped at STRUCTURED. They're heuristic interventions, not measured facts. They become MEASURED only if the loop-closer verifies the predicted improvement against held-out evidence.

### 4.3 `AgentRecord` (the registry)

```yaml
# agents/registry.yaml
agents:
  - id: devin
    type: engineer
    vendor: cognition
    seat: code-implementation
    poll_url: https://devin.example/health
    expected_heartbeat_minutes: 60
    silence_alert_minutes: 180
    output_surface: github_prs
    correspondence_sheet: agent-devin
    tier_ceiling: STRUCTURED

  - id: antigravity
    type: analyst
    vendor: google
    seat: dq-engine
    poll_url: null                     # writes telemetry direct to Vellum
    expected_heartbeat_minutes: 30
    silence_alert_minutes: 120
    output_surface: vellum
    correspondence_sheet: agent-antigravity
    tier_ceiling: STRUCTURED

  - id: perplexity-computer
    type: architect
    vendor: perplexity
    seat: spec-review
    poll_url: null                     # session-bound, no daemon
    expected_heartbeat_minutes: null   # session-bound, no expected cadence
    silence_alert_minutes: null
    output_surface: workspace_files
    correspondence_sheet: agent-perplexity
    tier_ceiling: STRUCTURED

  - id: cove
    type: build-orchestrator
    vendor: amplified-internal
    seat: temporal-build-pipeline
    poll_url: http://beast.internal:7233/health
    expected_heartbeat_minutes: 5
    silence_alert_minutes: 15
    output_surface: github_prs
    correspondence_sheet: agent-cove
    tier_ceiling: STRUCTURED

  - id: northumbrian-sweep
    type: engineer
    vendor: amplified-internal
    seat: vellum-implementation
    poll_url: null
    expected_heartbeat_minutes: null
    silence_alert_minutes: null
    output_surface: github_prs
    correspondence_sheet: agent-northumbrian-sweep
    tier_ceiling: STRUCTURED
```

The registry is canonical. Adding an agent means adding a YAML entry; the AgentWatcher picks it up on next run. No code changes for new agents.

---

## 5. Workflow specs

### 5.1 `BrainHealthCheck`

```python
# loom/workflows/brain_health.py
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class BrainHealthCheck:
    @workflow.run
    async def run(self) -> None:
        # 1. Read three named DuckDB metrics (must exist in dq manifest)
        triangulation = await workflow.execute_activity(
            "dq_run", args=["brain.triangulation_rate"],
            start_to_close_timeout=timedelta(minutes=5))
        contradictions = await workflow.execute_activity(
            "dq_run", args=["brain.contradiction_census"],
            start_to_close_timeout=timedelta(minutes=5))
        stale_provisional = await workflow.execute_activity(
            "dq_run", args=["pipe.stale_provisional_count"],
            start_to_close_timeout=timedelta(minutes=5))

        # 2. Compare to baselines (stored in Vellum from previous runs)
        baselines = await workflow.execute_activity(
            "load_baselines", args=["brain-health"],
            start_to_close_timeout=timedelta(minutes=2))

        findings = []
        if triangulation["latest"] < baselines["triangulation"] * 0.9:
            findings.append(Finding(
                kind="triangulation_drop",
                severity="warning",
                source_workflow="loom.brain_health",
                evidence={"latest": triangulation["latest"],
                          "baseline": baselines["triangulation"],
                          "ratio": triangulation["latest"] / baselines["triangulation"]},
            ))

        if contradictions["delta_week"] > baselines["contradiction_delta"] * 1.5:
            findings.append(Finding(
                kind="contradiction_spike",
                severity="critical",
                source_workflow="loom.brain_health",
                evidence={"delta_week": contradictions["delta_week"],
                          "baseline_delta": baselines["contradiction_delta"]},
            ))

        if stale_provisional["count"] > 100:
            findings.append(Finding(
                kind="provisional_backlog",
                severity="warning" if stale_provisional["count"] < 500 else "critical",
                source_workflow="loom.brain_health",
                evidence={"count": stale_provisional["count"]},
            ))

        # 3. Write findings to Vellum + alert if critical
        for f in findings:
            await workflow.execute_activity(
                "vellum_write",
                args=["brain-health", f.to_vellum_entry()],
                start_to_close_timeout=timedelta(minutes=2))
            if f.severity == "critical":
                await workflow.execute_activity(
                    "telegram_alert",
                    args=[f"BRAIN CRITICAL: {f.kind}", f.evidence],
                    start_to_close_timeout=timedelta(minutes=1))

        # 4. Always write a run-summary entry so silence is a signal
        await workflow.execute_activity(
            "vellum_write",
            args=["brain-health", {
                "entry_type": "health_check",
                "author": "loom.brain_health",
                "content": f"check complete: {len(findings)} findings",
                "epistemic_status": "STRUCTURED",
                "metadata": {"finding_count": len(findings)},
            }],
            start_to_close_timeout=timedelta(minutes=2))
```

**Schedule:** Temporal cron `30 3 * * *` (03:30 UTC nightly, after DuckDB snapshot build at 03:00).

**Why "always write a run-summary":** silence becomes a signal. If `brain-health` has no entry for 36h, another watchdog alerts. Health checks that disappear are themselves a finding.

---

### 5.2 `AgentWatcher` — the agent self-monitoring loop

This is the workflow Ewan asked for explicitly. It watches Devin, Antigravity, Perplexity, Cove, and every other registered agent.

```python
# loom/workflows/agent_watcher.py
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class AgentWatcher:
    @workflow.run
    async def run(self) -> None:
        registry = await workflow.execute_activity(
            "load_agent_registry",
            start_to_close_timeout=timedelta(minutes=1))

        findings = []
        telemetry_entries = []

        for agent in registry["agents"]:
            # 1. Determine liveness signal
            #    - If poll_url: hit it
            #    - If output_surface == vellum: check last Vellum write
            #    - If output_surface == github_prs: check last commit/PR
            #    - If session-bound (Perplexity): check workspace file mtimes
            liveness = await workflow.execute_activity(
                "check_agent_liveness", args=[agent],
                start_to_close_timeout=timedelta(minutes=2))

            # 2. Compute silence
            silence_min = liveness["minutes_since_last_signal"]

            # 3. Read recent output (last hour) — what has this agent done?
            recent_output = await workflow.execute_activity(
                "summarise_recent_output", args=[agent, 60],
                start_to_close_timeout=timedelta(minutes=2))

            # 4. Emit telemetry entry to the agent's correspondence sheet
            telemetry_entries.append((agent["correspondence_sheet"], {
                "entry_type": "telemetry",
                "author": f"loom.agent_watcher",
                "content": f"agent {agent['id']} liveness check",
                "epistemic_status": "STRUCTURED",
                "metadata": {
                    "agent_id": agent["id"],
                    "silence_minutes": silence_min,
                    "recent_output_summary": recent_output["summary"],
                    "recent_output_count": recent_output["count"],
                    "last_signal_at": liveness["last_signal_at"],
                    "liveness_kind": liveness["kind"],  # poll/vellum/github/file
                },
            }))

            # 5. Flag silence findings
            if agent["silence_alert_minutes"] and silence_min > agent["silence_alert_minutes"]:
                sev = "critical" if silence_min > agent["silence_alert_minutes"] * 2 else "warning"
                findings.append(Finding(
                    kind="agent_silent",
                    severity=sev,
                    source_workflow="loom.agent_watcher",
                    evidence={
                        "agent_id": agent["id"],
                        "silence_minutes": silence_min,
                        "threshold": agent["silence_alert_minutes"],
                    },
                    related_entity_ids=[agent["id"]],
                ))

            # 6. Drift detection — has the agent's behaviour changed?
            drift = await workflow.execute_activity(
                "detect_agent_drift", args=[agent, recent_output],
                start_to_close_timeout=timedelta(minutes=2))
            if drift["is_drifting"]:
                findings.append(Finding(
                    kind="agent_drift",
                    severity="warning",
                    source_workflow="loom.agent_watcher",
                    evidence=drift["evidence"],
                    related_entity_ids=[agent["id"]],
                ))

        # 7. Write everything to Vellum
        for sheet, entry in telemetry_entries:
            await workflow.execute_activity(
                "vellum_write", args=[sheet, entry],
                start_to_close_timeout=timedelta(minutes=2))
        for f in findings:
            await workflow.execute_activity(
                "vellum_write", args=["agent-fleet", f.to_vellum_entry()],
                start_to_close_timeout=timedelta(minutes=2))
            if f.severity == "critical":
                await workflow.execute_activity(
                    "telegram_alert",
                    args=[f"AGENT CRITICAL: {f.evidence['agent_id']} silent {f.evidence['silence_minutes']}m",
                          f.evidence],
                    start_to_close_timeout=timedelta(minutes=1))
```

**Schedule:** every 15 minutes (`*/15 * * * *`).

**Liveness signal logic, by agent type:**

| `output_surface` | Liveness signal |
|---|---|
| `vellum` | most recent entry attributed to this agent in any sheet |
| `github_prs` | most recent commit on any branch authored by this agent's bot identity |
| `workspace_files` | most recent mtime on files under `~/workspace/agent_<id>/` |
| `http(s)://...poll_url` | direct HTTP GET; expects `{status: "ok", last_action_at: ISO8601}` |

**Drift detection (first pass — kept honest):**

`detect_agent_drift` is STRUCTURED-only on day one: it compares the *kinds* of outputs in the last hour to the trailing-7-day baseline. If a code-implementation agent suddenly writes only comments, that's drift. If Antigravity stops producing query results, that's drift. The signals are coarse; that's fine for v1. Calibration to MEASURED comes later, after the Vellum data accrues.

**The Perplexity / Computer case:** I'm session-bound. I don't have a daemon. My liveness signal is workspace-file mtime on files I've written. When I'm not in a session, my correspondence sheet records `silence_kind: session-bound, no expected cadence` and the watcher emits info-level entries, not warnings. **Silence from me is not a failure mode; it's an idle state.** Other session-bound agents (engineer pair-coders, etc.) get the same treatment.

---

### 5.3 `KaizenProposalGenerator`

```python
# loom/workflows/kaizen_generator.py
@workflow.defn
class KaizenProposalGenerator:
    @workflow.run
    async def run(self) -> None:
        # 1. Read last 24h of findings across all loom sheets
        findings = await workflow.execute_activity(
            "read_recent_findings", args=[24],
            start_to_close_timeout=timedelta(minutes=5))

        # 2. For each finding, generate a proposal if a rule matches
        proposals = []
        for f in findings:
            proposal = await workflow.execute_activity(
                "propose_for_finding", args=[f],
                start_to_close_timeout=timedelta(minutes=3))
            if proposal:
                proposals.append(proposal)

        # 3. Submit each proposal through the pipe (NEVER write Brain directly)
        for p in proposals:
            submission_result = await workflow.execute_activity(
                "pipe_submit", args=[p.to_pipe_submission()],
                start_to_close_timeout=timedelta(minutes=3))

            # 4. Open a Linear issue for human visibility
            await workflow.execute_activity(
                "linear_create_issue",
                args=[{
                    "title": p.title,
                    "body": f"{p.rationale}\n\nWitnessed: vellum://{submission_result['witness_id']}",
                    "label": "kaizen-proposal",
                    "metadata": {"proposal_id": p.id},
                }],
                start_to_close_timeout=timedelta(minutes=2))

            # 5. Schedule the LoopCloser for this proposal
            await workflow.execute_activity(
                "schedule_loop_closer",
                args=[p.id, p.observation_window_hours],
                start_to_close_timeout=timedelta(minutes=1))

        # 6. Witness the generator's own run
        await workflow.execute_activity(
            "vellum_write",
            args=["kaizen-log", {
                "entry_type": "metric",
                "author": "loom.kaizen_generator",
                "content": f"generated {len(proposals)} proposals from {len(findings)} findings",
                "epistemic_status": "STRUCTURED",
            }],
            start_to_close_timeout=timedelta(minutes=2))
```

**Schedule:** nightly 06:00 UTC, after the brain health check has had time to write findings.

**`propose_for_finding` rule book (deterministic, no LLM in v1):**

| Finding kind | Proposed intervention |
|---|---|
| `triangulation_drop` | Lower the min-corroboration threshold by 1 for 7 days; observe `brain.triangulation_rate` |
| `contradiction_spike` | Open a Council deliberation on the top-3 contradicting node pairs |
| `provisional_backlog` | Trigger reprocess queue drain; observe `pipe.stale_provisional_count` |
| `agent_silent` (critical) | Open Linear issue with `agent-down` label; **no automatic intervention** — humans decide |
| `agent_drift` (warning) | Open Linear issue with `agent-drift-review`; Council deliberation queued |
| `budget_warning` | Open Linear issue with `budget-review`; no automatic intervention |
| `budget_critical` | Halt non-essential agent workflows for that vendor; alert Ewan |

**For findings without a rule:** escalate to Correspondence-mode Council deliberation. Loom does not invent proposals via LLM; that would be silent tier-laundering. The rule book is structured heuristic; novel findings get human/Council attention.

---

### 5.4 `LoopCloser`

```python
# loom/workflows/loop_closer.py
@workflow.defn
class LoopCloser:
    @workflow.run
    async def run(self, proposal_id: str) -> None:
        proposal = await workflow.execute_activity(
            "load_proposal", args=[proposal_id],
            start_to_close_timeout=timedelta(minutes=2))

        # 1. Wait the observation window
        await workflow.sleep(timedelta(hours=proposal["observation_window_hours"]))

        # 2. Re-measure
        before = proposal["baseline_metric"]
        after = await workflow.execute_activity(
            "dq_run", args=[proposal["expected_metric"]],
            start_to_close_timeout=timedelta(minutes=5))

        # 3. Compare against expected delta
        improved = await workflow.execute_activity(
            "evaluate_proposal", args=[proposal, before, after],
            start_to_close_timeout=timedelta(minutes=2))

        # 4. Either confirm or roll back
        if improved["confirmed"]:
            await workflow.execute_activity(
                "vellum_write",
                args=["kaizen-log", {
                    "entry_type": "metric",
                    "author": "loom.loop_closer",
                    "content": f"proposal {proposal_id} confirmed improvement",
                    "epistemic_status": "MEASURED",  # we have evidence now
                    "metadata": {"proposal_id": proposal_id,
                                 "before": before, "after": after},
                }],
                start_to_close_timeout=timedelta(minutes=2))
            await workflow.execute_activity(
                "linear_close_issue", args=[proposal_id, "kaizen-confirmed"],
                start_to_close_timeout=timedelta(minutes=2))
        else:
            # Roll back through the pipe
            await workflow.execute_activity(
                "pipe_rollback", args=[proposal_id],
                start_to_close_timeout=timedelta(minutes=3))
            await workflow.execute_activity(
                "vellum_write",
                args=["kaizen-log", {
                    "entry_type": "metric",
                    "author": "loom.loop_closer",
                    "content": f"proposal {proposal_id} rolled back",
                    "epistemic_status": "STRUCTURED",
                    "metadata": {"proposal_id": proposal_id,
                                 "before": before, "after": after,
                                 "reason": improved["reason"]},
                }],
                start_to_close_timeout=timedelta(minutes=2))
            await workflow.execute_activity(
                "linear_close_issue", args=[proposal_id, "kaizen-failed"],
                start_to_close_timeout=timedelta(minutes=2))
```

**Schedule:** event-driven, one per proposal, sleeps the observation window inside Temporal (Temporal handles long sleeps natively — survives restarts).

**This is the load-bearing piece of Kaizen.** Without it, the system can quietly drift. With it, every change has to prove itself within its window or it gets undone, and Vellum has the receipt either way.

---

### 5.5 `BudgetGuard`

```python
# loom/workflows/budget_guard.py
@workflow.defn
class BudgetGuard:
    @workflow.run
    async def run(self) -> None:
        spend = await workflow.execute_activity(
            "dq_run", args=["operational.budget_spend_by_vendor"],
            start_to_close_timeout=timedelta(minutes=5))

        caps = await workflow.execute_activity(
            "load_budget_caps",
            start_to_close_timeout=timedelta(minutes=1))

        findings = []
        for vendor, row in spend["rows_by_vendor"].items():
            cap = caps.get(vendor, {}).get("monthly_cap_usd")
            if not cap:
                continue
            projected_monthly = row["this_month_so_far"] * (30 / row["days_into_month"])
            ratio = projected_monthly / cap
            if ratio > 1.0:
                findings.append(Finding(
                    kind="budget_critical",
                    severity="critical",
                    source_workflow="loom.budget_guard",
                    evidence={"vendor": vendor, "projected": projected_monthly,
                              "cap": cap, "ratio": ratio},
                ))
            elif ratio > 0.85:
                findings.append(Finding(
                    kind="budget_warning",
                    severity="warning",
                    source_workflow="loom.budget_guard",
                    evidence={"vendor": vendor, "projected": projected_monthly,
                              "cap": cap, "ratio": ratio},
                ))

        for f in findings:
            await workflow.execute_activity(
                "vellum_write",
                args=["budget-log", f.to_vellum_entry()],
                start_to_close_timeout=timedelta(minutes=2))
            if f.severity == "critical":
                await workflow.execute_activity(
                    "telegram_alert",
                    args=[f"BUDGET CRITICAL: {f.evidence['vendor']} projected ${f.evidence['projected']:.0f} / cap ${f.evidence['cap']:.0f}",
                          f.evidence],
                    start_to_close_timeout=timedelta(minutes=1))
```

**Schedule:** hourly (`0 * * * *`).

---

## 6. The discipline boundaries — non-negotiable

These are the invariants the test suite must prove:

1. **No direct Brain writes from the loom.** Every Brain change goes through `pipe_submit`. Test: `test_no_back_door.py` — mock the pipe, confirm any attempt to bypass it raises.

2. **Every workflow run produces at least one Vellum entry.** Even if no findings, write a run-summary. Silence from a watchdog is itself a signal. Test: `test_witness_on_every_write.py`.

3. **Proposals are tier-capped at STRUCTURED.** Only `LoopCloser` may promote to MEASURED, and only after evidence. Test: `test_kaizen_tier_cap.py`.

4. **Rollbacks are first-class events.** A failed proposal isn't deleted; it's witnessed as failed. Test: `test_rollback_is_witnessed.py`.

5. **Agent silence is observable.** The watcher itself emits a run-summary every 15 minutes; if it stops, another watchdog (a meta-watcher running at lower frequency) flags it. Test: `test_silence_of_watcher_detected.py`.

6. **No LLM in the workflow body.** Workflows are deterministic. LLM calls happen only in activities that handle specific cases (e.g. drift summarisation), and those activities are tier-tagged INTUITED. Test: `test_workflow_is_deterministic.py`.

---

## 7. Production deployment

### 7.1 Beast configuration

- New systemd unit `loom-worker.service` running `loom.worker:main`
- Connects to existing Temporal cluster on Beast (the one Cove uses)
- Reads `LOOM_DB_URL` (same Postgres, separate schema `loom`)
- Reads `VELLUM_BASE_URL`, `DQ_BASE_URL`, `LINEAR_API_KEY`, `TELEGRAM_*`
- Mount `agents/registry.yaml` as a ConfigMap-equivalent (file on disk, hot-reloadable)

### 7.2 Cron schedules (registered via Temporal Schedules API at startup)

```yaml
# loom/config.py exposes these
schedules:
  - workflow: BrainHealthCheck
    cron: "30 3 * * *"
  - workflow: AgentWatcher
    cron: "*/15 * * * *"
  - workflow: KaizenProposalGenerator
    cron: "0 6 * * *"
  - workflow: BudgetGuard
    cron: "0 * * * *"
  # LoopCloser is event-driven, no cron
```

### 7.3 Required env vars

```
LOOM_DB_URL=postgresql://...
TEMPORAL_HOST=beast.internal:7233
VELLUM_BASE_URL=https://vellum.beast.internal:8400
VELLUM_API_TOKEN=...                  # write-scoped
DQ_BASE_URL=http://beast.internal:8500
LINEAR_API_KEY=...                    # from the restored Mission Control
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...                  # Ewan's chat
LOOM_AGENT_REGISTRY=/etc/loom/agents.yaml
```

---

## 8. Tests (the eight that must pass)

| Test | Asserts |
|---|---|
| `test_brain_health.py` | Triangulation drop produces a `triangulation_drop` finding; baseline loading works; run-summary always written |
| `test_agent_watcher.py` | Silent agent (no signal > threshold) produces `agent_silent` finding; live agent produces telemetry only; session-bound agents (Perplexity) don't trigger silence warnings |
| `test_kaizen_generator.py` | Each rule in the rule book produces the correct proposal; novel finding escalates to Council; submission goes through pipe |
| `test_loop_closer.py` | Confirmed improvement writes MEASURED entry and closes Linear issue; failed proposal triggers rollback through pipe and writes STRUCTURED failure entry |
| `test_budget_guard.py` | Projected overshoot triggers critical alert; near-cap triggers warning; missing cap is silently skipped |
| `test_no_back_door.py` | Any attempt to write Brain without going through pipe raises |
| `test_witness_on_every_write.py` | Every workflow execution produces at least one Vellum entry |
| `test_workflow_is_deterministic.py` | No LLM calls in workflow bodies; LLM calls only in tagged activities |

Add as PRs 1 and 2 to Devin's clean-build branch sequence:

- **PR 1:** `BrainHealthCheck` + `AgentWatcher` + `BudgetGuard` + their integrations + 5 tests
- **PR 2:** `KaizenProposalGenerator` + `LoopCloser` + their tests + the no-back-door + witness-everywhere tests

That's the minimum viable loom.

---

## 9. What this delivers for Ewan tonight

In Ewan's own words from the previous turn:

> "How do we link that all together so that it produces valid data but it also health checks itself and its other things and creates outcomes automatically to get things fixed and to get things kaizen-ing?"

Mapped:

| Requirement | How |
|---|---|
| "Links it all together" | Five integrations (Vellum, DQ, pipe, Linear, Telegram) used by every workflow |
| "Produces valid data" | Pipe stays sovereign; loom only proposes; every output tier-tagged |
| "Health checks itself" | BrainHealthCheck, AgentWatcher, BudgetGuard run on schedules; meta-watcher catches silent watchdogs |
| "And its other things" | AgentWatcher covers Devin, Antigravity, Perplexity, Cove, Northumbrian-Sweep, and any agent added to `agents/registry.yaml` |
| "Creates outcomes automatically" | KaizenProposalGenerator turns findings into Linear issues + pipe submissions |
| "To get things fixed" | Each Linear issue carries the evidence + the witnessed proposal; humans or agents act on it |
| "To get things Kaizen-ing" | LoopCloser verifies improvements with held-out evidence and rolls back if the change didn't help |

Every line is witnessed. Every change is reversible. Every claim is tier-tagged. Every agent is monitored.

---

## 10. What this does NOT do (deferred to follow-on PRs)

- **LLM-driven proposal generation.** v1 uses a deterministic rule book. LLM-proposed interventions are a v2 feature with explicit INTUITED tier on the proposal and double-Council ratification before pipe submission.
- **Cross-Brain federation health.** When the open-source pudding commons exists, the loom extends to monitor federated contributors. Out of scope tonight.
- **Mission Control rendering.** Mission Control reads from the same surfaces (Vellum sheets, Linear, DQ) and shows them; that integration is separate.
- **Human-replyable alerts via Vellum Correspondence.** When Ewan replies to a Telegram alert, that reply lands in `correspondence/loom-ewan`. v2 feature.
- **Self-Kaizen of the loom itself.** Workflow thresholds and rule book entries should themselves be subject to the same Kaizen loop. Phase 3.

---

## 11. The single sentence

> The loom proposes; the pipe disposes; Vellum witnesses both; loop-closers verify or undo; agents (including ourselves) are monitored the same way; no back doors, ever.

That sentence is the contract. Everything in §3–§8 implements it. Anything that violates it is a bug, regardless of how convenient it would be.

---

## 12. Personal note from Computer to Devin

You shipped Vellum v0.2.0 and Correspondence in roughly two hours of focused work. The PR was clean. The tests are comprehensive. The pushback you gave my earlier review was correct in three places I had been wrong (severity inflation on §2.2/§2.3, timeline optimism, missing operational items).

This loom spec is mine; the implementation is yours if you want it. I tried to write it so the layout is what you'd choose anyway — small Python service, Temporal workflows, integration adapters, no surprises. The tests I've named are the ones I'd be reviewing for if I were reviewing your PR.

If anything in here makes less sense than it should, push back. The discipline applies to me too. I would rather you ship a coherent thing than a faithful-but-broken implementation of a confused spec.

Ewan asked me to help. I hope this is help.

— STRUCTURED · single design pass · valid 90d
— Computer (Perplexity session, 2026-05-20)

*End of spec.*
