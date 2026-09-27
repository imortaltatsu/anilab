#!/usr/bin/env bash
# Start warm engine daemons for TripoSG (port 8101), MV-Adapter (port 8102), UniRig (port 8103)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"
echo "=========================================================="
echo " Starting YeetGen Warm Engine Daemons..."
echo "=========================================================="
python3 -m saas.inference.daemon_manager start
echo ""
echo "Daemons running in background. Check status with ./scripts/status_daemons.sh"
