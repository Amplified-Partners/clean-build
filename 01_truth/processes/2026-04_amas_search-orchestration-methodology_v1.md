---
title: AMAS - Amplified Multi-Engine Adaptive Search
date: 2026-04-18
version: 1
status: candidate
---

# AMAS: Amplified Multi-Engine Adaptive Search Methodology

**Purpose:** Methodology for choosing which search engine to use, how to phrase queries, and how to combine results from multiple engines.

## The Three Engines

| Engine | Strength | When to Use |
|--------|----------|-------------|
| **SearXNG (Beast)** | Private, 10Gbps, 70+ engine aggregation | General, technical, privacy-critical |
| **Brave Search** | Independent index, 669ms latency | Real-time, news, factual verification |
| **Tavily** | Source-credibility ranked | Citations, academic, evidence-based |

## Core Principle

> **The agent is the mind. The engines are its senses.**

## The AMAS Procedure

### 1. Query Decomposition (APEX-Searcher)

Before searching:
- **Planning:** What do we need to know?
- **Execution:** Run planned sub-queries

Don't retrieve to confirm what you think. Retrieve to discover what you don't know.

### 2. Engine Routing (Anthropic)

**Decision tree:**
```
Query type?
├── Technical/General → SearXNG
├── Real-time/News → Brave
└── Academic/Citations → Tavily
```

### 3. Failure Detection (WebRAgent)

Know when search is failing:
- Empty results
- Low-relevance snippets
- Contradictory sources
- Circular references

**Pivot strategy:**
- Reformulate query
- Switch engine
- Broaden then narrow

### 4. Result Fusion (AMAS)

Combine results from multiple engines:
- Deduplicate
- Source credibility weighting
- Cross-engine consistency check
- Confidence scoring

## Output

Not "search results" but **verified knowledge** with source attribution.
