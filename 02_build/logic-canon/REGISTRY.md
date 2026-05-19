# Logic Canon — Pattern Registry

> **What is this?** A toolbox of solved algorithmic patterns. Each module solves one problem. If you're building something and the problem matches, import the module — don't reinvent it.
>
> **How to use:** Find your problem below → import the module → pass your data.
>
> **Provenance:** Extracted from Nexus V2 (production trading engine, 6,500+ lines). Domain-specific language removed. Maths identical. Patterns universal.
>
> **Dependencies:** numpy, pandas (already in every Amplified system).

---

## Problem → Module Lookup

| I need to... | Module | Function |
|---|---|---|
| **Allocate budget across channels based on performance** | `adaptive_allocator` | `rebalance()` |
| **Detect when something is failing and cut it** | `adaptive_allocator` | `assess_channel()` |
| **Stop an autonomous system before it causes damage** | `circuit_breaker` | `CircuitBreaker.check()` |
| **Cap exposure / prevent over-concentration** | `circuit_breaker` | `CircuitBreaker.check_exposures()` |
| **Test new approaches without real-world risk** | `shadow_tester` | `generate_variants()` + `check_promotions()` |
| **Find the best parameters for a system** | `genetic_optimiser` | `run_tournament()` |
| **Rank N items by multiple weighted criteria** | `multi_factor_ranker` | `rank_items()` or `rank_simple()` |
| **Detect when the environment has shifted** | `regime_detector` | `RegimeDetector.update()` |
| **Scale system activity based on volatility** | `regime_detector` | `RegimeDetector.vol_scale` |
| **Detect redundancy between channels** | `correlation_monitor` | `check_correlations()` |
| **Convert scores into proportional budget splits** | `signal_normaliser` | `normalise()` |
| **Make constraints tamper-evident / immutable** | `ulysses_clause` | `UlyssesClause.check_constraint()` |
| **Audit-chain any sequence of actions** | `ulysses_clause` | `UlyssesClause.audit_chain` |

---

## Module Summaries

### 1. `adaptive_allocator` — Self-Healing Resource Allocation
**Problem:** N channels compete for fixed budget. Shift automatically toward winners, away from losers.
**Key maths:** Trailing Sharpe = `(mean / std) × √annualisation`. Kill if < -0.5. Boost if > 1.0. Mean-revert 10%/cycle. Cap change at 5%/cycle.
**Config knobs:** `kill_sharpe`, `boost_sharpe`, `max_change_per_cycle`, `mean_reversion_rate`

### 2. `circuit_breaker` — Autonomous Damage Prevention
**Problem:** Autonomous system could compound damage. Need hard stops.
**Key maths:** Daily loss > threshold → freeze N cycles. Cumulative drawdown > threshold → longer freeze. Vol targeting: `target_vol / realised_vol` scalar.
**Config knobs:** `max_daily_loss`, `max_cumulative_drawdown`, `target_vol`, `max_single_exposure`

### 3. `shadow_tester` — Risk-Free A/B Testing
**Problem:** Want to test new approaches without risk. Only promote when statistically better.
**Key maths:** Generate variants (±20% parameter perturbation). Track for 30+ days. Promote when: Sharpe beats live by ≥0.30 AND return beats by ≥3% AND max DD < 15%.
**Config knobs:** `num_variants`, `param_range`, `min_days`, `sharpe_beat_threshold`

### 4. `genetic_optimiser` — Evolutionary Parameter Search
**Problem:** Large parameter space, non-obvious interactions. Find best combination.
**Key maths:** Population of 50. Tournament selection (top 20%). Crossover (30%) + mutation (15%, gaussian). Elitism (top 2 unchanged). 10 generations.
**Config knobs:** `population_size`, `generations`, `mutation_rate`, `crossover_rate`, fitness weights

### 5. `multi_factor_ranker` — Cross-Sectional Ranking
**Problem:** Rank N items against each other using multiple weighted dimensions.
**Key maths:** Percentile-rank each factor → center at 0 → weighted sum = composite. Top 30% = strong signal.
**Config knobs:** `weights` dict, `long_threshold`, `short_threshold`

### 6. `regime_detector` — Environmental Shift Detection
**Problem:** Detect when operating environment has fundamentally changed. Scale activity.
**Key maths:** Signal > threshold → regime change. Confirmation readings prevent whiplash. Vol scalar = `target_vol / realised_vol`.
**Config knobs:** `caution_threshold`, `crisis_threshold`, `caution_scale`, `crisis_scale`, `invert`

### 7. `correlation_monitor` — Redundancy Detection
**Problem:** Two channels you thought were independent are doing the same thing.
**Key maths:** Pairwise Pearson correlation over rolling window. |corr| > 0.70 = redundant.
**Config knobs:** `window`, `warning_threshold`, `critical_threshold`

### 8. `signal_normaliser` — Opinions to Proportional Allocations
**Problem:** Convert scores of varying strength into proportional budget splits.
**Key maths:** `allocation = (signal / sum_of_all_signals) × budget`. Cap at max%. Floor at minimum useful size.
**Config knobs:** `max_allocation_pct`, `signal_threshold`, `min_allocation`

### 9. `ulysses_clause` — Tamper-Evident Constraints
**Problem:** Prevent operator (including future-you) from weakening rules under pressure.
**Key maths:** HMAC-SHA256 signed manifest. SHA-256 hash-chained audit log. Any modification detected.
**Config:** constraints dict + signing key

---

## Cross-Cutting Patterns

These modules compose. Common combinations:

| Use Case | Modules |
|---|---|
| **Marketing engine** | `multi_factor_ranker` (prioritise content) + `adaptive_allocator` (budget across channels) + `shadow_tester` (test new strategies) + `correlation_monitor` (detect overlap) |
| **Agent orchestration** | `circuit_breaker` (halt runaway agents) + `regime_detector` (scale activity by system health) + `ulysses_clause` (enforce governance) |
| **CRM intelligence** | `multi_factor_ranker` (lead scoring) + `genetic_optimiser` (tune parameters) + `adaptive_allocator` (resource allocation) |
| **Self-improving system** | `shadow_tester` (L2) + `genetic_optimiser` (L3) + `adaptive_allocator` (L1) — this IS the 3-tier Kaizen loop |

---

## The 3-Tier Kaizen Loop (all three modules together)

```
L1: adaptive_allocator  — DAILY  — reweight based on performance
L2: shadow_tester       — WEEKLY — A/B test parameter variants
L3: genetic_optimiser   — MONTHLY — evolve via genetic algorithm

Flow: L3 breeds → top survivors feed L2 → L2 promotes winners → L1 reweights live
```

Any system with tuneable parameters and measurable outcomes can use this loop.

---

*Devon-b3d8 | 2026-05-15 | Logic Canon v1.0*
*Provenance: Nexus V2 on Beast (Hetzner AX162-R) → domain-agnostic extraction*
