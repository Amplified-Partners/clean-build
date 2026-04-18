---
title: Three-Brain Data Isolation (Privacy by Architecture)
date: 2026-04-18
version: 1
status: candidate
---

# Three-Brain Data Isolation

**Purpose:** Maintain strict data isolation between Amplified knowledge, individual clients, and cross-client pattern sharing.

## The Three Brains

| Brain | Contains | Access |
|-------|----------|--------|
| **Amplified Brain** | Proprietary frameworks, research, patterns | Never visible to clients |
| **Per-Client Brain** | Client data, processes, business logic | Hard-isolated per client |
| **Federated/Network Brain** | PUDDING-labelled patterns only | Cross-client learning without data sharing |

## Isolation Rules

1. **Client agents never see Amplified Brain**
2. **Amplified agents never mix raw client data**
3. **Hard vault isolation** — separate storage, separate access
4. **Periodic audit** of isolation boundaries

## Federated Learning

When client process improves (e.g., to AMPS 7+):

1. Extract improvement **pattern** using PUDDING labels
2. **No raw data** in pattern extract
3. Store in Federated/Network Brain
4. Distribute to other clients via PUDDING matching

**Example:** Plumber's scheduling improvement pattern → restaurant's table booking system

## Privacy Guarantee

> **Network effects without data sharing.**

Each client benefits from collective learning. No client data is exposed.

## Why This Matters

- Privacy as **structural guarantee**, not policy
- Clients trust the architecture, not promises
- Compound learning without data risk
- Auditable, testable isolation

## Output

Privacy-preserving data architecture with provable isolation boundaries.
