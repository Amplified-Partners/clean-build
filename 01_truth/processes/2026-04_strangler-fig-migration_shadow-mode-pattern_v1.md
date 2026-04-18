---
title: Strangler Fig Migration (Shadow Mode Pattern)
date: 2026-04-18
version: 1
status: candidate
---

# Strangler Fig Migration Pattern

**Purpose:** Migrate from old systems to new AI-augmented systems without disruption.

## The Pattern

Named after the strangler fig tree that grows around an existing tree, eventually replacing it while the host remains alive.

## How It Works

```
Old System          New AI System
     |                    |
     |---- Shadow Mode --->|
     |     (observation)    |
     |                    |
     |---- Sidecar Mode --->|
     |   (AI assists)       |
     |                    |
     |---- Gradual ------>|
          (transfer)
     |                    |
     |---- Cutover ------>|
          (old retired)
```

## The Rule

**New system runs alongside old system before replacing it.**

## Implementation

### Phase 1: Shadow (Weeks 1-4)
- New AI system observes old system
- No data changes
- Generates recommendations
- Proves accuracy

### Phase 2: Sidecar (Weeks 5-8)
- New system assists old system
- Dual operation
- Human validates AI output
- Gradual trust building

### Phase 3: Gradual Transfer (Weeks 9-12)
- Move functions one at a time
- Old system still available
- Rollback possible
- Continuous validation

### Phase 4: Cutover (Week 13+)
- Old system retired
- New system primary
- Monitoring continues
- Emergency rollback plan

## Why This Matters

- **Zero downtime** — old system stays up
- **Risk mitigation** — rollback always possible
- **Trust building** — demonstrate before commit
- **Data safety** — no data loss during migration

## Application

Any system migration:
- Accounting software
- CRM replacement
- Process automation
- Knowledge system migration

**Never** "flip the switch" without shadow period.
