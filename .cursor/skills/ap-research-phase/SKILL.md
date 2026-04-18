---
name: ap-research-phase
description: Execute the research phase after internal planning. Targeted internet search for inspiration, structure, reassurance, or context. Use after /ce-brainstorm, before production.
---

# Research Phase (Amplified Partners)

**When to use:** After internal synthesis (/ce-brainstorm), before production. External validation phase.

## The Sequence

```
Phase 1: Internal synthesis (brainstorm with existing context)
         ↓
Phase 2: Research phase (THIS SKILL) — targeted internet search
         ↓
Phase 3: Opinion formation — merge internal/external
         ↓
Phase 4: Production — with explicit frame
         ↓
Phase 5: Reflection — wrap-up, stateless handover, compound
```

## Research Discipline

| Parameter | Rule |
|-----------|------|
| **Scope** | Specific blocker only |
| **Depth** | ≤3 assessed bits |
| **Tag** | [CURRENT BEST EVIDENCE] |
| **Synthesis** | Merge with internal knowledge |
| **Output** | Research digest with inline citations |

## Query Strategy

1. **Natural language** — not keywords
2. **Specific** — "agent workspace authority patterns 2025" beats "AI organization"
3. **Time-aware** — include year when relevant
4. **Multiple angles** — 2-3 query variants for broad topics

## Output Format

```markdown
## Research Digest: [Topic]

### Key Finding 1
**Claim:** Direct answer
**Evidence:** Facts, numbers, dates
**Source:** [URL]
**Status:** [CURRENT BEST EVIDENCE]

### Synthesis
Merged with internal knowledge:
- What aligns
- What contradicts
- What gaps remain

### Next Step
Proceed to Phase 3 (opinion formation) or flag [DECISION REQUIRED] if conflict is irreconcilable.
```

## Integration with CE Skills

- Use `/ce-brainstorm` before this phase (internal synthesis)
- Use `/ce-plan` after this phase (production planning)
- Use `/ap-qwen-handover` if research doesn't resolve blocker

## The Principle

Internal synthesis first, external validation second, merged opinion third. Never production from research alone. Never research from speculation.
