---
title: Trust Ramp (Four-Stage Autonomous Transition)
date: 2026-04-18
version: 1
status: candidate
---

# Trust Ramp (Four-Stage Autonomous Transition)

**Purpose:** Structured path from zero trust to autonomous AI operation for each client.

## The Four Stages

| Stage | Name | What Happens | Client Control |
|-------|------|--------------|----------------|
| 1 | **Shadow Mode** | AI observes, makes recommendations, human decides | 100% human |
| 2 | **Shadow Mode + Sidecar** | AI acts alongside, human reviews before commit | 90% human |
| 3 | **Shadow Mode + Auto-Approve** | AI acts, human reviews after | 50% human |
| 4 | **Autonomous** | AI operates, human sets goals and constraints | 20% human |

## Stage Details

### Stage 1: Shadow Mode (0-30 days)
- AI observes client operations
- Generates recommendations
- Human makes all decisions
- Build trust through accuracy

### Stage 2: Sidecar (30-60 days)
- AI proposes actions
- Human approves each action
- AI learns preferences
- Gradual handoff

### Stage 3: Auto-Approve (60-90 days)
- AI acts within defined blinkers
- Human reviews periodically
- Exceptions escalate
- Confidence building

### Stage 4: Autonomous (90+ days)
- AI operates within mission
- Human sets goals and constraints
- Periodic review
- Continuous improvement

## The Rule

**Never skip stages.** Trust is earned through demonstrated competence at each level.

## Exit Criteria per Stage

- AMPS score ≥7.0 for all processes
- Zero critical errors in last 30 days
- Client confidence score ≥8/10
- Explicit client approval to proceed

## Why This Matters

- **Safety** — no premature autonomy
- **Trust building** — demonstrated competence
- **Client comfort** — control reduces with confidence
- **Accountability** — clear stage gates
