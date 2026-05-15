---
title: Business Brain — AI Context Schema (19 fields)
date: 2026-05-14
version: 1
status: candidate
changelog:
  - version: 1
    date: 2026-05-14
    change: Initial commit — 19-field schema with 7 clusters.
    signed_by: Devon-4c30
---

# Business Brain — AI Context Schema

The 19-field rich context layer passed to AI for any high-fidelity call (triage / synthesis / rendering).

**Principle:** carefully chosen, mutually orthogonal, sparsely populated. Most fields are null on most calls. AI handles absence as information.

**Hard ceiling:** 20 fields. Currently at 19. To add a 20th, retire or merge an existing one.

**Discipline:** every field has a declared failure mode (`drop_breaks`). If you can't say what breaks when it's dropped, it doesn't belong here.

---

## Clusters

### Activity Context (4 fields)

| Field | Type | Required | drop_breaks |
|-------|------|----------|-------------|
| `pcf_activity_id` | string (e.g. "8.2.1.3") | yes | AI can't situate the query in the substrate's vocabulary; cross-business comparison breaks. |
| `entity_type` | enum: customer, job, resource, invoice, document, event, other | yes | AI can't pick the right schema slice; renders generic. |
| `current_state` | struct: {status, flags} | yes | AI talks about static facts when the query is about live state. |
| `recent_delta` | list[change_event] | no | AI misses the "what's new" half of every triage call. |

### Data Quality (3 fields)

| Field | Type | Required | drop_breaks |
|-------|------|----------|-------------|
| `tier` | enum: INTUITED, STRUCTURED, MEASURED, PROVEN | yes | AI over- or under-confidently renders. Silent-promotion failure mode. |
| `confidence` | float 0.0–1.0 | yes | AI can't carry the uncertainty envelope into rendering. |
| `provenance` | struct: {source, acquired_at, extractor, raw_hash} | yes | AI can't attribute. Radical-attribution principle dies at the edge. |

### Business Signature (4 fields)

| Field | Type | Required | drop_breaks |
|-------|------|----------|-------------|
| `tone` | enum: warm, terse, formal, salty, plain, brief | yes | AI renders in generic English; the business doesn't recognise its own voice. |
| `identity_self_description` | string (< 200 chars) | yes | AI loses the tonal envelope; renders correctly but soullessly. |
| `vocabulary_overrides` | map[string, string] (universal_term → local_term) | no | AI uses PCF terms instead of the business's terms. Sounds like a consultant. |
| `constraints` | list[string] (things explicitly out of scope) | no | AI suggests things the business has explicitly said no to. Trust collapses. |

### Temporal Context (2 fields)

| Field | Type | Required | drop_breaks |
|-------|------|----------|-------------|
| `rhythm` | struct: {peak_days, quiet_seasons, end_of_period_patterns} | no | AI surfaces wrong priority for the moment. |
| `temporal_marker` | struct: {now, day_of_week, time_of_day, week_in_month, quarter} | yes | AI can't read the rhythm even if rhythm is populated. |

### Audience Context (3 fields)

| Field | Type | Required | drop_breaks |
|-------|------|----------|-------------|
| `audience_role` | enum: owner, dispatcher, fitter, office_manager, caller, other | yes | AI surfaces the wrong 3 from the 19. Owner's 3 ≠ dispatcher's 3. |
| `audience_state` | struct: {previous_action, current_focus, mode} | no | AI breaks continuity. Asks them to repeat context they just gave. |
| `recent_interactions` | list[typed_exchange] (last 3-5) | no | AI forgets the conversation. Cardinality translator becomes amnesiac. |

### Analytical Context (2 fields)

| Field | Type | Required | drop_breaks |
|-------|------|----------|-------------|
| `applicable_insights` | list[insight_lens] | no | AI freelances analysis instead of using the declared attribution catalogue. Opinions replace formulas. |
| `substrate_alerts` | list[alert] | no | Python's findings don't reach the human. The substrate's voice gets muted. |

### Epistemic Context (1 field)

| Field | Type | Required | drop_breaks |
|-------|------|----------|-------------|
| `open_questions` | list[uncertainty] | no | AI papers over uncertainty instead of surfacing it. Radical-honesty principle dies at the edge. |

---

## The 19/3 Principle

- **Capture 19** at every surface (Linear, pipe, Brain).
- **Store 19** in the substrate (PostgreSQL).
- **AI reasons on 19** during triage/synthesis.
- **Render 3** when a human arrives — chosen by `audience_role` + `audience_state` + the moment.

The transmission layer (19→3 and 3→19) is the one operation deterministic logic categorically cannot do: cardinality rendering against a moving target of reader-type. That is what AI is for.

---

## Growth Pathway

To add a 20th field:
1. Identify which cluster it belongs in.
2. Write its `drop_breaks` line before its description. If you can't, it doesn't belong.
3. Check orthogonality against every existing field in its cluster. If overlap > 20% with any, merge or reject.
4. Bump schema version.

To retire a field:
1. Mark deprecated for one minor version.
2. Remove in next major version.
3. Migration: signatures using it carry it in a `deprecated_fields` block until cleanup.

---

*Devon-4c30 | 2026-05-14 | session devin-4c30b171b2074de7842c99f77e5093c1*
