---
title: PUDDING Value Mathematical Model (PVMM)
date: 2026-04-18
version: 1.0
status: candidate
---

# PUDDING Value Mathematical Model (PVMM)

**Purpose:** Determine whether a PUDDING connection is worth making before making it.

## The Formula

```
PV = (EVPI × Y × R) - (C + L(τ))
```

Run the PUDDING when **PV > 0**.

## Variables

| Variable | Meaning | Source |
|----------|---------|--------|
| **PV** | Pudding Value (net benefit) | Calculated |
| **EVPI** | Expected Value of Perfect Information | Decision theory |
| **Y** | Combination Yield (probability A+B produces C) | Empirical |
| **R** | Relevance Decay Discount | Taguchi |
| **C** | Cost to run PUDDING | Known |
| **L(τ)** | Taguchi Loss from domain velocity | Quality engineering |

## What It Answers

1. **Should we run this PUDDING?** (Pre-flight gate)
2. **How much effort justifies?** (Resource allocation)
3. **When re-run?** (Decay scheduling)
4. **Did it produce value?** (Post-hoc validation)

## Theoretical Foundations

- **Don R. Swanson** — Literature-Based Discovery, ABC model (1986)
- **Dixit & Pindyck** — Real Options Theory (1994)
- **Genichi Taguchi** — Quality Loss Function
- **Decision Theory** — Expected Value of Perfect Information

## Application

Before any PUDDING session:
1. Calculate PV threshold
2. If PV < 0: **Do not run**
3. If PV > 0: **Proceed**, prioritize by PV magnitude

**PUDDING score ≥ 18:** Build immediately  
**PUDDING score ≥ 13:** Build  
**PUDDING score ≥ 5:** Viable  
**PUDDING score < 5:** Kill it
