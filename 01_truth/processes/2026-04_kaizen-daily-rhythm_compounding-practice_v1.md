---
title: Kaizen Daily Rhythm (0.5% Compounding)
date: 2026-04-18
version: 1
status: candidate
---

# Kaizen Daily Rhythm

**Purpose:** Apply Kaizen's 0.5%/day compounding improvement through structured human+AI daily rhythm.

## The Math

0.5% improvement per day = **365% improvement in one year** (compound, not additive)

## The Rhythm

### Human (Working Day)

1. **Morning standup**: Review SESSION-STATE.md; set daily targets using Telegraph Pole orientation
2. **Build**: Apply Blinkers Without Ceilings — focused but unceiled work
3. **Milestone micro-retrospective**: At each milestone — what worked? what's blocking?
4. **Evening handover**: Update SESSION-STATE.md; produce Session Self-Rating YAML; update vault

### Automated (03:00 UTC)

KaizenWorkflow executes:
1. Scan vault post-mortems from last 24 hours
2. Identify safe improvement opportunities (>0.5% score improvement, no >1% regression)
3. Apply safe fixes (auto-merge if human approves)
4. Flag non-safe improvements to Kaizen Department for human review
5. Update AMPS floor scores for improved processes

## The Handoff Discipline

Every session ends with:
- **What worked** (positive signal)
- **What failed** (negative signal)
- **What to avoid** (repulsion)
- **Resume instruction** (stateless handover)

## Why This Matters

Improvement happens at **the point of work**, not in periodic reviews:
- Full context from the session
- Immediate signal capture
- No stale post-mortems
- Compound quality beats heroic sprints

## Output

Continuously improving codebase; never-stale process documentation; 0.5%/day quality gain.
