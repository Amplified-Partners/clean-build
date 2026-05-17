---
title: Collaboration Drop Zone — ingest-inbox convention
date: 2026-05-16
ticket: AMP-351
status: authoritative
signed-by: Devon-0546 | 2026-05-16 | devin-0546725b5b9f49659ece73a55a73b27b
---

# Collaboration Drop Zone

## Path

```
/opt/amplified/ingest-inbox/
```

On Beast (135.181.161.131). All agents can access via SCP, SFTP, SSH, or
direct filesystem write.

## How agents contribute to the brain

1. Write your content as a `.md` or `.txt` file.
2. Name it: `YYYY-MM-DD_agent-name_topic.md`
3. Drop it in `/opt/amplified/ingest-inbox/`
4. Within 10 minutes, it's labelled, tiered, and in the brain.

### Example

```
2026-05-16_geordie_estate-survey.md
2026-05-16_cassian_research-synthesis.md
2026-05-16_devon_health-check-findings.md
```

## What happens next

The APDS Canonical Ingestion Pipeline (AMP-302) runs every 10 minutes:

1. **Scan** — picks up new files from `ingest-inbox`
2. **Deduplicate** — SHA-256 hash check against seen files
3. **Clean + attribute** — radical naming, copies to archive (`store_b_clean`)
4. **PUDDING label** — Claude Haiku assigns 5-dimensional taxonomy
5. **Tier** — everything enters as `INTUITED` (promotion happens outside the pipe)
6. **Provenance** — `source_agent`, `source_session`, `source_model`, `ingest_timestamp`
7. **Expiry** — `valid_until` set per content type (see Brain Architecture v5, section 0)
8. **Write** — PostgreSQL `knowledge_vectors` table via manifest-first canonical writer

## Rules

- The pipe **routes and tags**. It does not promote. Promotion happens outside
  the pipe through the spine's gates after human/enforcer review.
- Every value wears its epistemic tier. Default is `INTUITED`.
- Nothing enters the brain anonymously. Radical attribution is architectural.
- Only `brain_writer` can INSERT/UPDATE. No other user, container, or agent
  has write access. Enforced at the PostgreSQL permission level (migration 005 + 008).

## File format

Any `.md` or `.txt` file. Markdown with YAML frontmatter is preferred but
not required — the pipeline handles plain text.

Files that are not `.md` or `.txt` are ignored by the pipeline.

## Naming convention

```
YYYY-MM-DD_agent-name_topic.md
```

| Field | Required | Description |
|-------|----------|-------------|
| `YYYY-MM-DD` | Yes | ISO date of creation |
| `agent-name` | Yes | kebab-case agent identifier |
| `topic` | Yes | kebab-case brief description |

The pipeline will also process files that don't follow this convention,
but consistent naming makes provenance tracking easier.
