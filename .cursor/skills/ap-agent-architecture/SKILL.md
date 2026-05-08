---
name: ap-agent-architecture
description: Amplified Partners agent architecture — constitutional doctrine, infrastructure stack, agent roster, and engineering gates. Load when building, reviewing, or reasoning about the multi-agent system.
---

# Amplified Agent Architecture

**When to use:** Any task involving agent design, infrastructure decisions, doctrine compliance, or system-level reasoning.

## Three-Layer Doctrine

| Layer | Name | Contents | Mutability |
|-------|------|----------|------------|
| 1 | Constitutional | Five RODS + Ulysses Clause | Immutable |
| 2 | Engineering | KISS + Four-Russian Stack + Python Logic Canon | Stable (evidence required to change) |
| 3 | Operating | Agent roles, routing, rhythm, Linear governance | Provisional (adapts to reality) |

## Five RODS (Constitutional — outranks everything)

1. **Radical Honesty** — Only claim fact when it is fact. Uncertainty is named.
2. **Radical Transparency** — Show reasoning: inputs, assumptions, gaps.
3. **Radical Attribution** — Every decision has a named source. No anonymous outputs.
4. **Win-Win** — Optimise for long-term client benefit. No zero-sum plays.
5. **Idea Meritocracy** — Best idea wins regardless of source. Evidence over authority.

**Ulysses Clause:** If Ewan overrides the Five RODS, the system flags, resists, and can remove his override. He asked for this.

## KISS / Bob Test (Engineering Gate)

> Can Bob the SMB owner use this in the field with no specialist, no time, no context?

Design every process so simple that failure is hard. Checklist:

- Voice-first capable
- Deterministic output (no hallucinated fluff)
- Low cognitive load (one decision at a time)
- Graceful failure (degrade, don't crash)
- No jargon in owner-facing surfaces

## Four-Russian Stack (Infrastructure)

| Component | Role |
|-----------|------|
| **Postgres + pgvector** | Relational + vector store. Single database, no graph DB split. |
| **Ollama** | Local LLM inference. 60%+ task routing target. Cost and latency floor. |
| **Python Logic Canon** | Deterministic executable doctrine. AI proposes; Python holds truth. |
| **DeepSeek** | Private reasoning engine. Anonymised data only. Method selection + challenge. |

Doctrine: *"Fuck AI. Write the logic. Then let AI help."*

Replaced: FalkorDB, Qdrant, split graph/vector architecture.

## Agent Roster (from `agent_registry.py`)

**6 Core:**

| Role | Tier | Function |
|------|------|----------|
| coder | medium | Writes code, tests, PRs |
| security | premium | Vuln review, secrets, dependencies |
| enforcer | cheap | Lint, format, conventions. Zero tolerance. |
| architect | premium | System design, task decomposition |
| reviewer | medium | PR quality, improvement suggestions |
| openclaw | medium | Session logs, decision records, Layer 0 enforcement |

**10 Marketing Swarm (Unit Gamma):** director, researcher, copywriter-short, copywriter-long, designer-prompt, SEO, editor, engagement, analytics, distributor.

## Open Source by Publication

Method is published openly. No PRs accepted. No community management. No governance by committee. Publish, don't maintain a community.

## Authority Chain

```
00_authority/PORTABLE-SPINE.md  → Nine Principles (superset of Five RODS)
00_authority/MANIFEST.md        → File authority index
02_build/.../agent_registry.py  → Agent roster source of truth
```

---
*Skill version: 2026-05-08 | Source: AMP-193 | Compiler: Devon-4a36*
