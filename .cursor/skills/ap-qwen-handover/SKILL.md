---
name: ap-qwen-handover
description: Execute stateless handover to Qwen (local LLM) when parking a process. Use when the problem-solving ladder is exhausted and escalation is needed.
---

# Qwen Stateless Handover (Amplified Partners)

**When to use:** After two attempts + research, still stuck. Park to Qwen, end session cleanly.

## The Handoff

```
Problem-solving ladder exhausted
         ↓
Write escalation note (YAML frontmatter)
         ↓
Qwen holds the problem
         ↓
Restart guaranteed
```

## YAML Format

```yaml
---
title: <short blocker description>
date: YYYY-MM-DD
status: parked
escalation_type: known-class | novel-decision
impact: low | medium | high
confidence: 0.0-1.0
attempts: 2
researched: yes | no
blocking_decision: <one sentence>
resolver_tier: qwen | ewan
---
```

## Steps

1. **Document attempts**: What was tried, what failed
2. **Research summary**: ≤3 assessed bits, tagged [CURRENT BEST EVIDENCE]
3. **Specific blocker**: Exact step/file/function/decision where stuck
4. **Write to**: `03_shadow/job-wrapups/YYYY-MM-DD_<short-job>_wrapup.md`
5. **Signal Qwen**: Both outcome and context
6. **End session**: Cleanly. Qwen guarantees restart.

## Routing

- **Known-class blocker** → Qwen resolves, writes resolution, triggers new agent automatically
- **Novel decision** → Qwen routes to Ewan with terse briefing, Ewan decides, Qwen triggers new agent

**Nothing is lost. No human needs to remember to restart.**
