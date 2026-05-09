#!/usr/bin/env bash
# docker-user-firewall.sh — DOCKER-USER iptables chain rules for Beast
# =====================================================================
# Prevents Docker's port-publishing from bypassing UFW by inserting rules
# into the DOCKER-USER chain (processed before DOCKER-FORWARD).
#
# Allows: localhost, Tailscale mesh, Traefik public ports (80/443).
# Drops: everything else inbound to Docker-published ports.
#
# Usage: Run via systemd unit (docker-user-firewall.service) before docker.
#        Can also be run manually: sudo bash docker-user-firewall.sh
#
# Signed-by: Devon-abaf | 2026-05-09 | session devin-abaf337e1eda492f85af1d26fa1614b9

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
EXTERNAL_IF="${BEAST_EXTERNAL_IF:-eth0}"        # External network interface
TAILSCALE_CIDR="100.64.0.0/10"                 # Tailscale IP range
DOCKER_BRIDGE_CIDR="172.16.0.0/12"             # Docker bridge networks
LOCALHOST_CIDR="127.0.0.0/8"                    # Loopback

# Public ports (Traefik only)
PUBLIC_TCP_PORTS="80,443"

# ─── Flush existing DOCKER-USER rules ────────────────────────────────────────
iptables -F DOCKER-USER 2>/dev/null || true

# ─── Rule 1: Allow established/related connections (stateful) ─────────────────
iptables -A DOCKER-USER -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN

# ─── Rule 2: Allow loopback (localhost access to containers) ──────────────────
iptables -A DOCKER-USER -s "${LOCALHOST_CIDR}" -j RETURN

# ─── Rule 3: Allow Tailscale mesh (remote admin via VPN) ─────────────────────
iptables -A DOCKER-USER -s "${TAILSCALE_CIDR}" -j RETURN

# ─── Rule 4: Allow Docker bridge networks (inter-container) ──────────────────
iptables -A DOCKER-USER -s "${DOCKER_BRIDGE_CIDR}" -j RETURN

# ─── Rule 5: Allow public Traefik ports from anywhere ────────────────────────
iptables -A DOCKER-USER -i "${EXTERNAL_IF}" -p tcp -m multiport --dports ${PUBLIC_TCP_PORTS} -j RETURN

# ─── Rule 6: DROP all other inbound on external interface ────────────────────
iptables -A DOCKER-USER -i "${EXTERNAL_IF}" -j DROP

# ─── Final: RETURN for anything not matched (safety) ─────────────────────────
iptables -A DOCKER-USER -j RETURN

echo "[docker-user-firewall] Rules applied on ${EXTERNAL_IF}:"
iptables -L DOCKER-USER -v -n --line-numbers
