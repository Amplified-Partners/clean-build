---
name: logic-canon
description: Shared algorithmic toolbox for all Amplified Partners systems. Use when you need adaptive allocation, circuit breakers, A/B testing, genetic optimisation, multi-factor ranking, regime detection, correlation monitoring, signal normalisation, or tamper-evident constraints.
---

# Logic Canon — Shared Algorithmic Toolbox

**Location:** `02_build/logic-canon/`
**Registry:** `02_build/logic-canon/REGISTRY.md` (full problem→module lookup table)
**Dependencies:** numpy, pandas

## When to reach for this

Before writing any of the following patterns from scratch, check if Logic Canon already solves it:

- Allocating resources across N competing channels based on performance
- Stopping a system before it causes cascading damage
- Testing new approaches in parallel without real-world risk
- Finding optimal parameters for a tuneable system
- Ranking items by multiple weighted criteria
- Detecting environmental regime shifts
- Detecting redundancy / overlap between channels
- Converting confidence scores into proportional allocations
- Enforcing tamper-evident constraints

## Quick import

```python
from logic_canon import adaptive_allocator, circuit_breaker, shadow_tester
from logic_canon import genetic_optimiser, multi_factor_ranker, regime_detector
from logic_canon import correlation_monitor, signal_normaliser, ulysses_clause
```

## The 3-Tier Kaizen Loop

```
L1: adaptive_allocator  — DAILY  — reweight based on performance
L2: shadow_tester       — WEEKLY — A/B test parameter variants  
L3: genetic_optimiser   — MONTHLY — evolve via genetic algorithm
```

Any system with tuneable parameters + measurable outcomes can use all three together.

## Key design principles

- **Zero infrastructure dependencies.** Pure functions + simple classes. No database, no API, no config files.
- **Domain-agnostic.** No trading language. Works for marketing, agents, CRM, content, anything.
- **Composable.** Modules work independently or together. Combine as needed.
- **All maths documented.** Every formula is in the module docstring. No black boxes.
