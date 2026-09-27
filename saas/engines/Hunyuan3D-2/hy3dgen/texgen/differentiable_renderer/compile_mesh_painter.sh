#!/usr/bin/env bash
# Build mesh_processor C++ extension (Linux).
set -euo pipefail
cd "$(dirname "$0")"
python_bin="${PYTHON:-python}"
"$python_bin" -m pip install -e . --no-build-isolation
