---
title: Component Types — 15-type artefact classification standard
date: 2026-05-17
version: 1
status: authoritative
---

<!-- markdownlint-disable-file MD013 -->

## Purpose

This file defines the **15 canonical component types** for classifying artefacts across the Amplified Partners estate. Every artefact — code, documentation, research, transcript, configuration — maps to exactly one component type. This taxonomy applies going forward to all new artefacts and is retroactively applied to the existing corpus via the pre-upload sort scanner.

This taxonomy classifies **what an artefact does** in the system, not what format it is in.

## The 15 Component Types

| Type | What it is | Examples |
|------|-----------|----------|
| **entry** | Entry point, landing page, root document, README, onboarding material. The first thing you read. | `README.md`, `ONBOARDING.md`, root index files, getting-started guides |
| **service** | A running service, API, server, or daemon definition. Something that listens and responds. | API specs, FastAPI routers, service definitions, endpoint docs, MCP server specs |
| **worker** | Background processor, batch job, cron task, async handler. Does work without being asked in real time. | Cron scripts, Temporal workflows, batch processors, scheduled jobs, vault-monitor runs |
| **connector** | Integration, bridge, adapter, sync mechanism. Connects one system to another. | API client wrappers, sync scripts, webhook handlers, channel integrations, MCP connectors |
| **model** | Data model, schema, type definition, ontology, entity structure. Defines the shape of data. | Database schemas, YAML schema definitions, type specs, entity relationship docs, data dictionaries |
| **store** | Storage definition, database config, vault structure, archive layout. Where data lives. | Vault maps, archive READMEs, database configs, storage architecture docs, knowledge-base structure |
| **pipeline** | Multi-step processing chain, workflow, ingestion flow, build pipeline. Ordered sequence of stages. | CI/CD workflows, ingestion pipelines, APDS stages, content atomisation flows, build processes |
| **orchestrator** | Coordination logic, routing, agent management, task distribution. Decides who does what. | Agent routing docs, orchestrator specs, SHARED-BOARD, task distribution logic, fleet management |
| **guard** | Safety, validation, enforcement, access control, compliance. Prevents bad things. | Authority docs, governance rules, validation schemas, security checklists, access rules, enforcers |
| **scorer** | Evaluation, ranking, measurement, rubric, quality assessment. Assigns a number to quality. | Scoring rubrics, quality rubrics, PUDDING scoring, visual polish scores, confidence frameworks |
| **agent** | Agent definition, persona, capability profile, behavioural contract. Defines what an agent is and does. | Agent profiles, SOUL.md, AGENTS.md, persona definitions, skill files, capability registers |
| **test** | Test, validation, verification, proof, QA artefact. Proves something works. | Test scripts, validation results, QA reports, verification docs, test plans |
| **config** | Configuration, settings, environment definition, parameters. Knobs and dials. | `.env` templates, YAML configs, deployment settings, parameter files, feature flags |
| **telemetry** | Logging, monitoring, observability, metrics, session records, transcripts, voice notes. Raw signal. | Session logs, transcripts, voice notes, monitoring output, health check results, daily reports |
| **glue** | Everything else. Narrative, context, notes, drafts, WIP, uncategorised. The connective tissue. | Session notes, drafts, narratives, context capsules, scratch docs, uncategorised inbox items |

## Rules

1. **Every artefact gets exactly one type.** No multi-tagging.
2. **When uncertain, classify as `glue`** and flag `needs_human_review`.
3. **The type describes function, not format.** A markdown file describing an API is `service`, not "documentation".
4. **`glue` is the honest catch-all**, not a failure. Narrative, context, and connective tissue are real work.
5. **Classification is heuristic.** The pre-upload sort scanner assigns types based on path, filename, content patterns, and YAML metadata. Human review overrides heuristic.

## Classification Signals (for automated scanners)

The scanner uses these signals in priority order:

1. **Directory path** — strongest signal (e.g., `00_authority/` → `guard`, `transcripts/` → `telemetry`)
2. **Filename keywords** — direct matches (e.g., `AGENTS.md` → `agent`, `README.md` → `entry`)
3. **YAML frontmatter** — metadata fields like `source_type`, `tags`
4. **Content patterns** — headings, structure, keyword density in first 500 chars
5. **Fallback** — `glue` with `needs_human_review`

---

*Signed-by: Devon | 2026-05-17 | Session 294b46afcdee47d5b250d328d61103c2*
