#!/usr/bin/env bash
# Check status of warm engine daemons
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"
python3 -m saas.inference.daemon_manager status
