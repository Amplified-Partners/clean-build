# Beast Infrastructure Hardening (AMP-289)

Fixes Docker firewall bypass and restricts internal port exposure to localhost + Tailscale only.

## Problem

Docker daemon writes iptables rules directly, bypassing UFW. Any port published with `0.0.0.0:PORT:PORT` is reachable from the public internet regardless of UFW rules. Multiple Beast services currently expose internal ports globally.

## Solution — Four Phases

| Phase | What | Risk | Rollback |
|-------|------|------|----------|
| 1 | DOCKER-USER iptables chain | Low | `systemctl stop docker-user-firewall` |
| 2 | Compose port rebinding to 127.0.0.1 | Low | Revert sed changes, `docker compose up -d` |
| 3 | PostgreSQL pg_hba.conf | Medium | Remove volume mount, restart postgres |
| 4 | AppArmor agent profiles | Medium | Remove `security_opt`, restart containers |

## Files

```
hardening/
  docker-user-firewall.sh       # Phase 1: iptables rules script
  docker-user-firewall.service  # Phase 1: systemd unit (before docker)
  pg_hba.conf                   # Phase 3: PostgreSQL HBA template
  apparmor-agent-container.profile  # Phase 4: AppArmor profile
  apply-hardening.sh            # Deployment script (all phases)
  README.md                     # This file
```

## Deployment

```bash
# All phases at once:
sudo bash apply-hardening.sh

# Or one phase at a time:
sudo bash apply-hardening.sh --phase 1
sudo bash apply-hardening.sh --phase 2
sudo bash apply-hardening.sh --phase 3
sudo bash apply-hardening.sh --phase 4
```

## Verification

```bash
# Phase 1: Check DOCKER-USER chain
sudo iptables -L DOCKER-USER -v -n --line-numbers

# Phase 2: Confirm no public listeners (should only show 80/443)
ss -tlnp | grep -v '127.0.0.1' | grep -v '::1'

# Phase 3: Test postgres rejects non-allowed connections
docker exec cove-postgres psql -U cove -c "SELECT 1;"  # should work (local)

# Phase 4: Check AppArmor enforcement
aa-status | grep amplified-agent
```

## Dependencies

- **AMP-136**: Tailscale container must be running for Tailscale access to work. The DOCKER-USER chain pre-allows 100.64.0.0/10 regardless.
- **AMP-282**: Temporal gRPC port 7233 has a separate application-level issue. Port rebinding does not worsen it.

## Network Architecture (Post-Hardening)

```
Internet ─── [135.181.161.131] ─── UFW ─── iptables
                                              │
                                         DOCKER-USER chain
                                              │
                              ┌────────────────┼────────────────┐
                              │                │                │
                         ACCEPT 80/443    ACCEPT 100.64/10   DROP *
                         (Traefik)        (Tailscale)        (all else)
                              │                │
                              ▼                ▼
                    ┌─── amplified-net ───┐   Tailscale mesh
                    │  postgres  redis    │   (remote admin)
                    │  litellm   langfuse │
                    │  temporal  searxng  │
                    │  openclaw  voice    │
                    │  entities  ...      │
                    └─────────────────────┘
```

---
*Signed-by: Devon-abaf | 2026-05-09 | session devin-abaf337e1eda492f85af1d26fa1614b9*
