---
title: OpenClaw Sovereign Fleet
date: 2026-05-02
version: 1
status: candidate
signed-by: Devon | 2026-05-02 | devin-701075c43e444229aa32f993bf60b36a
---

# OpenClaw Sovereign Fleet

Three IBAC-governed agent entities running as Docker containers with Cedar-based access control.

## Entities

| Entity | Role | Model | What it does |
|--------|------|-------|-------------|
| **Kimmy** | Orchestrator | Kimi K2 (Moonshot) | Routes tasks, coordinates fleet, triggers Tier 3 ops |
| **Alpha** | Arbiter | Claude Sonnet 4 (Anthropic) | Approves destructive operations, validates intent tokens |
| **Charlie** | Plumber | DeepSeek V4 | Hands-on coding in worktrees, needs analyst approval to write |

## IBAC Policy Tiers

| Tier | Who | What | Approval |
|------|-----|------|----------|
| 1 | All agents | Read files, git log, grep, view metrics | Auto-allow |
| 2 | Charlie | Write files in `/workspace/worktrees/` | Analyst must approve |
| 3 | Kimmy, Alpha | Merge PR, deploy production, execute shell | Arbiter + intent token |
| **Deny** | Nobody | Read policy files or `.env` | Blocked unconditionally |

## Quick start

```bash
# First time
./scripts/bootstrap.sh

# Or manually:
cp .env.template .env          # edit with your keys
make setup                     # build images + create workspaces
make up                        # start fleet

# Operations
make status                    # container status
make health                    # health check all entities
make logs                      # tail all logs
make logs-kimmy                # tail one entity
make validate-policies         # test Cedar policies
make test                      # run IBAC unit tests
```

## Directory structure

```
sovereign-fleet/
├── docker-compose.yml          # Production stack
├── .env.template               # Environment variables
├── Makefile                    # Operations interface
├── policies/
│   ├── prod.cedar              # Production IBAC policies
│   └── dev.cedar               # Development (relaxed) policies
├── agent/
│   ├── Dockerfile              # Agent container image
│   ├── pyproject.toml          # Python dependencies
│   ├── src/
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── config.py           # Configuration models
│   │   ├── ibac.py             # Cedar IBAC policy engine
│   │   ├── actions.py          # Action definitions
│   │   ├── llm.py              # LiteLLM integration
│   │   └── health.py           # Health check
│   └── tests/
│       └── test_ibac.py        # IBAC policy tests
├── entity_configs/
│   ├── kimmy.yaml              # Orchestrator config
│   ├── alpha.yaml              # Arbiter config
│   └── charlie.yaml            # Plumber config
└── scripts/
    ├── bootstrap.sh            # First-time setup
    └── validate-policies.py    # Policy validation + smoke tests
```

## API endpoints (per entity)

Each entity exposes the same FastAPI server on port 8000:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check (used by Docker + monitoring) |
| `/identity` | GET | Entity name, role, model, IBAC status |
| `/action` | POST | Execute an IBAC-governed action |
| `/chat` | POST | Direct LLM chat using entity's model |

## Dependencies

- Docker + Docker Compose V2
- LiteLLM proxy (already running on Beast — `INFRASTRUCTURE.md`)
- Tailscale auth key (for VPN mesh — optional for local dev)

## Integration with existing infrastructure

The fleet connects to the LiteLLM proxy already running on `amplified-core` (Hetzner).
Traefik ports are offset to avoid conflicts with the existing Traefik instance.
See `02_build/INFRASTRUCTURE.md` for the full server manifest.
