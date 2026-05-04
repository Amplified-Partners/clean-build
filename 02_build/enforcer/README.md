# enforcer

Health monitoring and enforcement for Amplified Partners infrastructure on Beast.

## What It Does

Runs 5 health checks on 10-minute cycles across all Beast services. Monitors container health, API responsiveness, database connectivity, session hygiene, and security posture. Alerts on degradation before failures cascade.

See `ENFORCER-SPEC.md` for the canonical spec and `enforcer.py:142-166` for the check list.

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

## Known Issue (flagged for follow-up)

The five check functions (`_check_redis`, `_check_falkordb`, `_check_postgres`, `_check_qdrant` in `checks/database_health.py`, `check_docker_health` in `checks/docker_health.py`, `check_security` in `checks/security_check.py`) are declared `async` but use **synchronous, blocking I/O** inside (`redis.Redis.ping`, `socket.connect_ex`, `docker.from_env`, `subprocess.run`). When scheduled via `asyncio.gather` in `enforcer.py:177`, the blocking calls prevent the event loop from making progress — so checks effectively run sequentially, and the FastAPI `/health` endpoint cannot respond while a cycle is in flight.

This contradicts the documented behaviour in `ENFORCER-SPEC.md` ("All checks run concurrently, so total time is the slowest check, not the sum").

**Production impact:** under degraded conditions (services timing out at 2s each) total cycle time can be ~10s instead of ~2s; Docker's own healthcheck on this container can also flap during that window. Source-repo bug, preserved verbatim by the AMP-77 merge so behaviour is unchanged from what is currently deployed on Beast.

**Fix path:** swap to `redis.asyncio.Redis`, `asyncio.open_connection`, `asyncio.create_subprocess_exec`, or wrap blocking calls in `loop.run_in_executor`. Tracked separately from this merge.

### `fail2ban_enabled` config flag is accepted but ignored

`checks/security_check.py:check_security` accepts a `fail2ban_enabled` argument (passed from `config.yaml` and `enforcer.py:164`) but never references it in the function body. The function only checks firewall and SSH-key auth — fail2ban is silently skipped regardless of the flag. `ENFORCER-SPEC.md` lists fail2ban as one of the security checks, so the spec and implementation disagree.

**Production impact:** the `fail2ban_enabled: true` config setting on Beast does nothing today. Fail2ban status is not actually monitored by the enforcer.

**Fix path:** add a `subprocess.run(['systemctl', 'is-active', 'fail2ban'], ...)`-style probe (or, since the enforcer runs in-container, a host-mount or DBus call) when `fail2ban_enabled` is true; merge its result into the security details. Tracked separately from this merge.

---

*Extracted from Beast `/opt/amplified/apps/enforcer/` by Devon | 2026-04-30 | session `aa4d863ad679468692e75a40b8825358`*
*Merged into `02_build/enforcer/`: Devon | 2026-05-04 | session devin-1bdaf31798874921940598bed17ca9e3 | AMP-77 spine cleanup*
