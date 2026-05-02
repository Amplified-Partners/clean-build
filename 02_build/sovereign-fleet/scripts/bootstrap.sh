#!/usr/bin/env bash
# OpenClaw Sovereign Fleet — Bootstrap Script
# Run once on a fresh host to set up the fleet.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLEET_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== OpenClaw Sovereign Fleet Bootstrap ==="
echo "Fleet directory: $FLEET_DIR"
echo ""

# 1. Check Docker
if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker is not installed."
    echo "Install: https://docs.docker.com/engine/install/"
    exit 1
fi
echo "[ok] Docker found: $(docker --version)"

# 2. Check Docker Compose
if ! docker compose version &>/dev/null; then
    echo "ERROR: Docker Compose V2 is not available."
    exit 1
fi
echo "[ok] Docker Compose: $(docker compose version --short)"

# 3. Create .env if missing
if [ ! -f "$FLEET_DIR/.env" ]; then
    cp "$FLEET_DIR/.env.template" "$FLEET_DIR/.env"
    echo "[ok] .env created from template — edit with your keys"
else
    echo "[ok] .env already exists"
fi

# 4. Create workspace directories
for entity in Entity_Kimmy Entity_Alpha Entity_Charlie; do
    dir="$FLEET_DIR/../$entity"
    mkdir -p "$dir"
    echo "[ok] Workspace: $dir"
done

# 5. Build images
echo ""
echo "Building agent images..."
cd "$FLEET_DIR"
docker compose build

echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your Tailscale auth key and LiteLLM config"
echo "  2. Run: make up"
echo "  3. Check: make health"
