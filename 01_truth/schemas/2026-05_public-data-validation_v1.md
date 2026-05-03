---
title: "Public-data validation — three-band verdict scheme"
id: "public-data-validation-v1"
version: 1
created: 2026-05-03
last_validated: 2026-05-03
type: document
topic_type: schema
status: candidate
ticket: AMP-66
parent_ticket: AMP-59
signed_by: "Devon-9a6b, 2026-05-03, devin-9a6bd256bd7c4a90a083a471fa94a810"
---

<!-- markdownlint-disable-file MD013 -->

# Public-data validation — three-band verdict scheme

**Date:** 2026-05-03
**Author:** Devon-9a6b (session `devin-9a6bd256bd7c4a90a083a471fa94a810`)
**Ticket:** AMP-66 (parent AMP-59)
**Companion to:** `2026-03_validation-methodology_v2.md` (PUDDING 2026 label-validity gate; not replaced).

## 0. What this is

A pragmatic verdict scheme for "is this insight backed by real public data
that we can fetch right now?" — applied per-insight on top of the existing
PUDDING 2026 STATUS field.

This document describes:

- the three-band verdict scheme;
- the four reusable test classes;
- the per-class evidence rules;
- how this composes with the PUDDING 2026 label-validity gate (it does not
  replace it; it sits one layer below it).

The first reference implementation lives in
`02_build/validators/retail/` (AMP-66). Sibling tickets AMP-64/65/67/68
build the equivalent for trades, hospitality, professional services, and
universal verticals.

## 1. The three bands

| Verdict      | Condition                                                                                              |
|--------------|---------------------------------------------------------------------------------------------------------|
| `PROVEN`     | Public data quantitatively confirms the claim at the granularity claimed. Specific test-class thresholds in §3. |
| `PLAUSIBLE`  | Data consistent with claim but underpowered, OR one leg of the recipe needs client data to fully validate, OR the recipe is purely-internal and has published research support. |
| `DISPROVEN`  | Public data contradicts the claim (signal absent; correlation null; distribution does not match).        |

`DEFERRED` is a fourth band reserved for recipes that **must not** be run
from an automated session (ToS-bound scraping, legal review pending, PII risk).
`DEFERRED` ≠ `PLAUSIBLE`: we are not estimating support, we are saying "do not
run this here at all".

`INCONCLUSIVE` from `2026-03_validation-methodology_v2.md` folds into
`PLAUSIBLE`. `REFUTED` equals `DISPROVEN`. The three-band scheme is
deliberately coarser than the methodology v2 RAEI/PRS/AMPS rubrics — it
answers a different question (data presence) and runs cheaper.

## 2. The four test classes

| Test class    | Question answered                                                                          | Evidence shape                                                                  |
|---------------|--------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| existence     | "Is the claimed data available at the claimed granularity?"                                | source URLs + status codes + sample rows; `n_reachable / n_sources`              |
| base_rate     | "Is the population proportion within the claimed range?"                                   | Wilson-CI 95% binomial proportion + claim-range overlap                          |
| correlation   | "Are the two series correlated as claimed?"                                                | Pearson + Spearman r, p-value, n, sign-match                                     |
| distribution  | "Does the observed distribution exceed the claim's threshold?"                             | mean, σ, z-score relative to threshold                                           |

A runner may compose multiple test classes (e.g. `existence + distribution`
in INS-067). The combined verdict takes the **lowest** band of the
constituent verdicts unless explicitly overridden in the runner with
documented reasoning.

## 3. Per-class verdict thresholds (defaults)

### 3.1 Existence

- `PROVEN` — every required source returns 2xx with non-empty payload at the claimed granularity.
- `PLAUSIBLE` — at least one source reachable; one source skipped because key is required.
- `DISPROVEN` — no required source returns a non-empty payload.

### 3.2 Base rate

- `PROVEN` — observed proportion within `[claim_lower, claim_upper]` AND Wilson 95% CI lies inside `[claim_lower − tol, claim_upper + tol]`.
- `PLAUSIBLE` — observed in range but CI wider than tolerance band (underpowered).
- `DISPROVEN` — observed outside `[claim_lower, claim_upper]`.

Default tolerance band: 0; runners may relax for low-n claims.

### 3.3 Correlation

- `PROVEN` — `|r| ≥ r_min` AND `p ≤ p_max` AND `n ≥ n_min` AND sign matches expected.
- `PLAUSIBLE` — `|r| ≥ r_min/2` AND sign matches; underpowered.
- `DISPROVEN` — `|r| < r_min/2` OR sign mismatch.

Defaults: `r_min = 0.6`, `p_max = 0.01`, `n_min = 12`, `expected_sign = +1`.

### 3.4 Distribution

- `PROVEN` — observed mean exceeds threshold by ≥ `z_min` standard deviations in the claimed direction.
- `PLAUSIBLE` — exceeds threshold but by less than `z_min` σ.
- `DISPROVEN` — does not exceed threshold OR direction wrong.

Default: `z_min = 1.0`.

## 4. Evidence bundle shape

Every verdict file is `02_build/validators/<vertical>/results/<INS-NNN>/verdict.json` and
contains:

```json
{
  "insight_id": "INS-067",
  "title": "...",
  "vertical": "Retail",
  "verdict": "PROVEN",
  "test_class": "existence+distribution",
  "summary": "<1-line>",
  "evidence": [
    {
      "test": "existence",
      "claim": "...",
      "n_sources": 12,
      "n_reachable": 12,
      "n_skipped_keyless": 0,
      "n_failed": 0,
      "sources": [{"source": "...", "url": "...", "status": 200, "sha256": "...", "sample": [...]}]
    },
    {"test": "distribution", "mean": 153.5, "stdev": 159.9, "threshold": 5.0, "z": 0.93, ...}
  ],
  "notes": [...],
  "confidence": 88,
  "run_at_utc": "2026-05-03T20:48:55Z",
  "git_sha": "<sha>",
  "session_id": "devin-...",
  "signed_by": "Devon-9a6b"
}
```

Each `sources[]` item carries the SHA-256 of the raw response so a verdict
is reproducible: re-run, hash, compare.

## 5. Where the scheme is used

- **Catalogue**: each retail entry in `01_truth/schemas/research-index/00-insight-catalogue_v1.md`
  has a `**VALIDATION (AMP-66):**` line appended after `**STATUS:**`, recording verdict + test
  class + confidence + run date + signer. Existing fields are not modified.
- **APDS routing**: the existing `02_build/routing/score_to_graph.py` already accepts a
  verdict-band field for FalkorDB Recipe nodes. Promotion path is documented in the AMP-59
  master plan; this PR does not yet write into FalkorDB.
- **Master report**: vertical-level rollups can read `results/INS-NNN/verdict.json` files and
  produce a deterministic table.

## 6. Relationship to PUDDING 2026 validation methodology v2

| Layer                                   | Question                                                                | Source of truth                                  |
|-----------------------------------------|-------------------------------------------------------------------------|--------------------------------------------------|
| PUDDING label validity (methodology v2) | Is the label structurally correct + inter-rater-reliable?               | `2026-03_validation-methodology_v2.md`           |
| Public-data validation (this doc)        | Is the claim backed by data we can fetch right now?                     | this document                                    |
| RAEI / PRS / AMPS / MASHUP rubrics       | Is the recipe production-ready and worth shipping to a client?          | methodology v2                                    |
| Catalogue STATUS field                   | High-level lifecycle stage (CONFIRMED-EXTERNAL / HYPOTHESIS / PROVEN)   | `00-insight-catalogue_v1.md`                     |

The four layers are not redundant — each answers a different question. The
public-data verdict is **additive** to STATUS, not a replacement.

## 7. Operational notes

- Public sources used in the retail reference implementation (no key
  required): Police.uk, ONS Beta API, Nomis, GOV.UK content API, Land
  Registry CCOD service page, BoE statistical database, DfT port stats,
  DESNZ sub-national energy.
- Public sources behind a free key: Companies House, Met Office DataPoint,
  EPC. Validators read the key from env (`COMPANIES_HOUSE_API_KEY` etc.)
  and downgrade to `PLAUSIBLE` when absent. Verdicts upgrade automatically
  on the next run after the key is added.
- ToS-bound or legal-review-pending sources (e.g. competitor-listing
  scraping for INS-077) are **DEFERRED** and skipped by the automated
  pipeline.

## 8. Known limitations

1. The scheme treats public-data presence as a sufficient condition for
   `PROVEN`. For a stricter scheme that also requires positive client-side
   replication, see methodology v2 §3.
2. Verdict bands are coarser than methodology v2 rubric scores. Use both:
   verdict for routing/triage, rubrics for ship/no-ship.
3. `DEFERRED` is operational, not informational. A `DEFERRED` recipe may
   later become `PROVEN`/`PLAUSIBLE`/`DISPROVEN` once the operational gate
   clears (legal review, client consent, etc.).

## 9. Changelog

- v1 (2026-05-03, Devon-9a6b) — initial schema, retail vertical reference implementation.

---

Signed,

**Devon-9a6b**
Devin session `9a6bd256bd7c4a90a083a471fa94a810`
2026-05-03
