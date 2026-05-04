# enforcer

Health monitoring and enforcement for Amplified Partners infrastructure on Beast.

## What It Does

Runs 6 health checks on 10-minute cycles across all Beast services. Monitors container health, API responsiveness, database connectivity, disk usage, and service dependencies. Alerts on degradation before failures cascade.

## Monitored Services

- Container health (38/40 containers)
- FalkorDB (graph database)
- Qdrant (vector database)
- PostgreSQL
- Ollama (LLM inference)
- LiteLLM (LLM routing proxy)
- Temporal (workflow orchestration)
- MinIO (object storage)
- SearXNG (metasearch)

---

*Extracted from Beast `/opt/amplified/apps/enforcer/` by Devon | 2026-04-30 | session `aa4d863ad679468692e75a40b8825358`*
