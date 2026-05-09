#!/usr/bin/env bash
# apply-hardening.sh — Deploy Beast infrastructure hardening (AMP-289)
# =====================================================================
# Run on Beast as root. Applies all four phases of hardening.
#
# Usage: sudo bash apply-hardening.sh [--phase N]
#   --phase 1  DOCKER-USER firewall only
#   --phase 2  Compose port rebinding only
#   --phase 3  PostgreSQL pg_hba.conf only
#   --phase 4  AppArmor profiles only
#   (no flag)  All phases
#
# Signed-by: Devon-abaf | 2026-05-09 | session devin-abaf337e1eda492f85af1d26fa1614b9

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMPLIFIED_DIR="/opt/amplified"
SECURITY_DIR="${AMPLIFIED_DIR}/security"
PHASE="${1:-all}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

# ─── Phase 1: DOCKER-USER Firewall ───────────────────────────────────────────
phase_1() {
    log "Phase 1: Installing DOCKER-USER firewall rules..."

    mkdir -p "${SECURITY_DIR}"
    cp "${SCRIPT_DIR}/docker-user-firewall.sh" "${SECURITY_DIR}/docker-user-firewall.sh"
    chmod +x "${SECURITY_DIR}/docker-user-firewall.sh"

    cp "${SCRIPT_DIR}/docker-user-firewall.service" /etc/systemd/system/docker-user-firewall.service
    systemctl daemon-reload
    systemctl enable docker-user-firewall.service
    systemctl start docker-user-firewall.service

    log "Phase 1 complete. Verify: iptables -L DOCKER-USER -v -n"
}

# ─── Phase 2: Compose Port Rebinding ─────────────────────────────────────────
phase_2() {
    log "Phase 2: Rebinding exposed ports to 127.0.0.1..."

    # Cove orchestrator (sovereign-fleet-repo)
    local COVE_SF="${AMPLIFIED_DIR}/sovereign-fleet-repo/02_build/cove-orchestrator/docker/docker-compose.yml"
    if [ -f "${COVE_SF}" ]; then
        sed -i 's/- "5432:5432"/- "127.0.0.1:5432:5432"/' "${COVE_SF}"
        sed -i 's/- "7233:7233"/- "127.0.0.1:7233:7233"/' "${COVE_SF}"
        sed -i 's/- "8080:8080"/- "127.0.0.1:8080:8080"/' "${COVE_SF}"
        sed -i 's/- "4000:4000"/- "127.0.0.1:4000:4000"/' "${COVE_SF}"
        sed -i 's/- "3000:3000"/- "127.0.0.1:3000:3000"/' "${COVE_SF}"
        log "  Patched: ${COVE_SF}"
    fi

    # Cove orchestrator (agent-stack)
    local COVE_AS="${AMPLIFIED_DIR}/agent-stack/cove-orchestrator/docker/docker-compose.yml"
    if [ -f "${COVE_AS}" ]; then
        sed -i 's/- "5432:5432"/- "127.0.0.1:5432:5432"/' "${COVE_AS}"
        sed -i 's/- "7233:7233"/- "127.0.0.1:7233:7233"/' "${COVE_AS}"
        sed -i 's/- "8080:8080"/- "127.0.0.1:8080:8080"/' "${COVE_AS}"
        sed -i 's/- "4000:4000"/- "127.0.0.1:4000:4000"/' "${COVE_AS}"
        sed -i 's/- "3000:3000"/- "127.0.0.1:3000:3000"/' "${COVE_AS}"
        sed -i 's/- "8888:8080"/- "127.0.0.1:8888:8080"/' "${COVE_AS}"
        log "  Patched: ${COVE_AS}"
    fi

    # OpenClaw agents
    local OPENCLAW="${AMPLIFIED_DIR}/apps/openclaw-agents/docker-compose.yml"
    if [ -f "${OPENCLAW}" ]; then
        sed -i 's/- "8100:8100"/- "127.0.0.1:8100:8100"/' "${OPENCLAW}"
        log "  Patched: ${OPENCLAW}"
    fi

    # Voice agent
    local VOICE="${AMPLIFIED_DIR}/../amplified-voice-agent/docker-compose.yml"
    if [ -f "${VOICE}" ]; then
        sed -i 's/- "8080:8080"/- "127.0.0.1:8080:8080"/' "${VOICE}"
        log "  Patched: ${VOICE}"
    fi
    # Also check /opt/amplified-voice-agent path
    local VOICE2="/opt/amplified-voice-agent/docker-compose.yml"
    if [ -f "${VOICE2}" ]; then
        sed -i 's/- "8080:8080"/- "127.0.0.1:8080:8080"/' "${VOICE2}"
        log "  Patched: ${VOICE2}"
    fi

    # Sovereign fleet (fleet-traefik ports — diagnostic only)
    local FLEET="${AMPLIFIED_DIR}/sovereign-fleet-repo/02_build/sovereign-fleet/docker-compose.yml"
    if [ -f "${FLEET}" ]; then
        # These use env vars with defaults, patch the defaults
        sed -i 's/\${TRAEFIK_HTTP_PORT:-8180}:80/127.0.0.1:\${TRAEFIK_HTTP_PORT:-8180}:80/' "${FLEET}"
        sed -i 's/\${TRAEFIK_HTTPS_PORT:-8443}:443/127.0.0.1:\${TRAEFIK_HTTPS_PORT:-8443}:443/' "${FLEET}"
        sed -i 's/\${TRAEFIK_DASHBOARD_PORT:-8181}:8080/127.0.0.1:\${TRAEFIK_DASHBOARD_PORT:-8181}:8080/' "${FLEET}"
        log "  Patched: ${FLEET}"
    fi

    log "Phase 2 complete. Restart affected stacks: docker compose up -d"
    log "  NOTE: Inter-container communication via Docker DNS is NOT affected."
}

# ─── Phase 3: PostgreSQL pg_hba.conf ─────────────────────────────────────────
phase_3() {
    log "Phase 3: Installing pg_hba.conf..."

    mkdir -p "${SECURITY_DIR}"
    cp "${SCRIPT_DIR}/pg_hba.conf" "${SECURITY_DIR}/pg_hba.conf"

    log "  pg_hba.conf installed to ${SECURITY_DIR}/pg_hba.conf"
    log "  To activate, add to postgres service in docker-compose.yml:"
    log "    volumes:"
    log "      - /opt/amplified/security/pg_hba.conf:/var/lib/postgresql/data/pg_hba.conf"
    log "  Then: docker compose restart postgres"
    log ""
    log "  WARNING: Ensure POSTGRES_PASSWORD uses scram-sha-256 (default for PG16+)."
    log "  Verify with: docker exec <container> psql -U cove -c \"SHOW password_encryption;\""
    log ""
    log "Phase 3 complete."
}

# ─── Phase 4: AppArmor Agent Sandboxing ──────────────────────────────────────
phase_4() {
    log "Phase 4: Installing AppArmor profile for agent containers..."

    local APPARMOR_DIR="/etc/apparmor.d"
    if [ ! -d "${APPARMOR_DIR}" ]; then
        log "  ERROR: AppArmor not installed. Install with: apt install apparmor apparmor-utils"
        return 1
    fi

    cp "${SCRIPT_DIR}/apparmor-agent-container.profile" "${APPARMOR_DIR}/amplified-agent"
    apparmor_parser -r -W "${APPARMOR_DIR}/amplified-agent"

    log "  AppArmor profile 'amplified-agent' loaded."
    log "  To apply to containers, add to docker-compose.yml services:"
    log "    security_opt:"
    log "      - \"apparmor=amplified-agent\""
    log "    cap_drop:"
    log "      - ALL"
    log "    security_opt:"
    log "      - \"no-new-privileges:true\""
    log "    read_only: true"
    log "    tmpfs:"
    log "      - /tmp"
    log "      - /var/tmp"
    log ""
    log "Phase 4 complete."
}

# ─── Main ─────────────────────────────────────────────────────────────────────
case "${PHASE}" in
    --phase)
        shift
        case "${1:-}" in
            1) phase_1 ;;
            2) phase_2 ;;
            3) phase_3 ;;
            4) phase_4 ;;
            *) echo "Usage: $0 [--phase 1|2|3|4]"; exit 1 ;;
        esac
        ;;
    all)
        phase_1
        echo ""
        phase_2
        echo ""
        phase_3
        echo ""
        phase_4
        ;;
    *)
        echo "Usage: $0 [--phase 1|2|3|4]"
        exit 1
        ;;
esac

log "Done. Run 'ss -tlnp | grep -v 127.0.0.1' to verify no unexpected public listeners."
