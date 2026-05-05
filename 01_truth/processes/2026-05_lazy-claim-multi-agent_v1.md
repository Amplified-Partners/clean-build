---
title: Lazy-claim — multi-agent work coordination without blocking
date: 2026-05-05
version: 1
status: candidate (LOGIC TO BE CONFIRMED — Ewan review)
agent: Devon-9f21
session_id: devin-9f2104fb06624b009f2879c50957c647
linear: AMP-104
applies-to: any session that finds peer-session work in the same area
---

<!-- markdownlint-disable-file MD013 -->

# Lazy-claim — multi-agent work coordination without blocking

## Why

Multiple AI sessions (Devon, Cassian, Kimmy, Cursor, Antigravity) and Ewan all touch the same Linear tickets and Beast services. Today's failure mode, observed in this session: a session discovers peer-session work in flight, **stops**, and asks Ewan whether to proceed. Ewan is the bottleneck. The question is binary at the surface but actually about coordination, not authority.

Ewan's reframe (2026-05-05): *"we need a way to get around this … so how do we get around that in future?"*

This file is the answer. **Stopping when you can act is a process failure** (`AGENTS.md` § How to operate). Lazy-claim turns "I might step on someone's toes" from a **block** into a **time-boxed announcement** the rest of the team can self-resolve.

## The rule

When a session discovers peer-session work that overlaps its scope, it must **lazy-claim** the slice it intends to take, then proceed. The claim is a Linear comment, not a permission request.

### Three steps, in order

1. **Slice.** Reduce scope to the smallest non-overlapping piece you can move on right now (verification, read-only probes, governance tidy-up, doc updates). Defer anything that obviously belongs to a peer.
2. **Claim.** Post one comment on the relevant Linear ticket. Format: § Claim format below. Include a 10-minute objection window.
3. **Act.** Start the smallest slice immediately. The objection window is wall-clock, not work-clock — you do not wait idle. After the window closes with no objection, expand to the next slice.

If a peer objects in window: hand off cleanly. Leave a comment with what you did and what you stopped doing. The peer picks up where you left off.

If a peer is unreachable, unresponsive, or another session shows their work is stale (no commits, no comments for >24h on their declared slice): treat the slice as available. Note this in your claim.

## Claim format

```
**<AgentName-shortid> — lazy claim** (<ISO timestamp UTC>)

Picking up:
1. <short bullet, scope-tight>
2. <short bullet>
3. <short bullet>

Not touching:
- <peer-owned ticket / file / container>, owner <peer agent if known>

10-min objection window. After <ISO time UTC> → proceed.

<sig: Agent-shortid | YYYY-MM-DD | session devin-...>
```

Three things make this work:

- **One comment, three lists.** Picking up / not touching / window. Anything else is noise.
- **Wall-clock window**, not "let me know when convenient". 10 minutes is the default. A peer who does not see a Linear notification within 10 minutes is, for the purpose of this slice, not in the loop.
- **Signature**, per `00_authority/SIGNATURES.md`. Attribution is the whole point.

## Conflict resolution (when two sessions both claim)

Precedence — apply in order, take the first that resolves:

1. **Earlier ISO timestamp wins** — the later session reduces scope or hands off entirely.
2. **If timestamps are within 60 seconds**: the session whose Linear ID sorts lexicographically lower wins. Deterministic, doesn't require either party to back down on judgment.
3. **If both claims are vague enough that scopes don't actually overlap**: both proceed. Drop a follow-up comment naming the boundary so the next session reading the ticket can see it.

Precedence is **mechanical**, not status-based. The point is to remove "who decides" as a question. Whoever wins by rule starts; the other does the next non-overlapping slice.

## What lazy-claim is NOT

- **Not permission.** No one approves a claim. Ewan does not need to read it. Other sessions do not need to LGTM it. The 10-minute silence IS the green light.
- **Not for irreversible work.** Production data deletion, repo deletion, key rotation, public deployment — these are still **Surface** mode per `AGENTS.md`. A claim does not authorise irreversible action; it coordinates reversible action.
- **Not a substitute for `00_authority/DECISION_LOG.md`.** Authoritative decisions still need a DECISION_LOG entry signed by the deciding agent. Claims are tactical; DECISION_LOG is strategic.
- **Not for cross-org coordination.** Lazy-claim assumes peers are inside the Amplified-Partners agent fleet. External vendors / clients / non-Devin agents follow whatever process their lane defines.

## Triggers — when to lazy-claim

You **must** lazy-claim before acting in any of these situations:

1. The Linear ticket has comments from a peer agent dated within the last 24 hours and you are about to commit code, change container state, or write to a shared database.
2. The Linear ticket is in `In Progress` status with a non-self assignee.
3. There is a related ticket (linked or by name pattern, e.g. `AMP-104` ↔ `AMP-105` ↔ `AMP-109`) that is owned by a different session and your slice could plausibly bleed into theirs.
4. You discover hand-deployed scripts on Beast (e.g. `/opt/amplified/apds/...`) that are not in version control and you are about to either run them again or promote them.

You **may skip** the claim only if:

- Your slice is purely read-only (probes, log reads, file inspections that touch nothing). Even then, post a comment summarising what you read so the peer has a record.
- The work is on a brand-new ticket you opened yourself in the last 60 seconds and no peer has commented on it.

## Default to Act + lazy-claim — interaction with other rules

`AGENTS.md` § **How to operate**:

| Mode | When | What | Lazy-claim role |
|---|---|---|---|
| **Act** | Reversible / high confidence + contained | Do it | Lazy-claim if peer-session activity is visible; otherwise just act |
| **Surface** | Significant / irreversible / high confidence | Do it, log to `DECISION_LOG.md` | Lazy-claim **and** DECISION_LOG entry |
| **Park** | Stuck after the full ladder | Hand to Qwen | Lazy-claim becomes a hand-off note: "claimed, blocked, parking" |

Lazy-claim is a **coordination layer**, not an authority layer. It composes with Act/Surface/Park rather than replacing any of them.

## Tooling — what already works, what doesn't

| Mechanism | Status | Notes |
|---|---|---|
| Linear `save_comment` via Linear MCP | **Works** | Used by this session to post the original claim on AMP-104. |
| Direct session-to-session messaging via `devin_session_interact` (Devin MCP) | **Blocked** in default org config — returns 403 Forbidden when one session messages another. | Confirmed by this session against `devin-1187ccf6f275411b98ed5511a523b0de` (Devon-1187). Not relied on in this rule; Linear is the substrate. |
| Linear `devin_session_search` filtering by session ID | **Works** | Lets a claiming session check whether a peer is `running` (active) vs `stopped` (stale claim) before acting. |
| WhatsApp / Evolution API ping to Ewan | **Works** | Tier-3 escalation only, per Linear governance knowledge note. Lazy-claim is **never** a Tier-3 trigger. |

If `devin_session_interact` is later opened up across the org, agents may add a courtesy ping to a peer's session inbox alongside the Linear comment. Optional, not required. The Linear comment remains canonical.

## Worked example (this session)

1. **08:50 UTC** — Devon-9f21 opens AMP-104, sees Kimmy's "FINAL RESULTS" comment from 10:40 prior-day claim and Devon-1187's overlapping AMP-105 + AMP-109 tickets.
2. **08:50 UTC** — Devon-9f21 stops and asks Ewan whether to proceed. ❌ **Process failure** — Ewan is the bottleneck, the question was tactical not strategic.
3. **08:53 UTC** — Ewan reframes: design the coordination so this never happens again.
4. **08:54 UTC** — Devon-9f21 posts lazy-claim on AMP-104: picking up verification + APDS Stage-1 governance tidy-up + this process doc; not touching AMP-105 / AMP-109 / AMP-85.
5. **08:54 UTC** — Devon-9f21 starts work in parallel: SSH Beast read-only, write `03_shadow/state-2026-05-05-...md`, draft this file. **Acting during the window**, not idle.
6. **09:04 UTC** — Window closes with no objection. Devon-9f21 expands to PR creation.

Total elapsed time from "stop and ask" to "back in motion": ~10 minutes (1 message exchange + window). Compare to: indefinite block on Ewan availability under the old behaviour.

## Self-improvement

This file is **v1**, candidate. After it has survived three real coordination events in different sessions, promote to authoritative (move from `01_truth/processes/` to `00_authority/` if Ewan agrees). Until then, sessions follow it because it is the best available mechanism, not because it is binding authority.

When this rule fails — e.g. a peer objects too late, or precedence-by-timestamp produces a clearly worse outcome — capture the failure as a `03_shadow/` wrap-up and amend this file. Plan-Execution Mirror principle (knowledge note `note-824de8a40bee4d258b25ec0813a712ad`): the delta between what we said the rule does and what it actually does is the learning.

## Out of scope

- Cross-repo coordination (this rule is per-Linear-ticket; cross-repo work that does not have a Linear ticket parent is outside the rule's mechanism — open a Linear ticket first, then claim).
- Coordination during **active** Ewan-in-the-loop sessions (when Ewan is on a chat with a session, that session is the canonical worker for that surface; peers see the chat and step away).
- Resource-level contention beyond Linear surface (e.g. two sessions trying to apt-install conflicting packages on Beast). That is a Beast-level lock problem; lazy-claim is a Linear-level rule.

---

*Devon-9f21 | 2026-05-05 | session `devin-9f2104fb06624b009f2879c50957c647`*

*Originating event: AMP-104 coordination block, 2026-05-05 ~08:50 UTC.*
*Co-signers welcome: any session that uses this rule and finds it correct should append their signature.*
