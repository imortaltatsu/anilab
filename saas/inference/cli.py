#!/usr/bin/env python3
"""CLI entry for game-ready inference (used by the SaaS worker)."""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `python saas/inference/cli.py` without installing the package.
_SAAS = Path(__file__).resolve().parents[1]
if str(_SAAS.parent) not in sys.path:
    sys.path.insert(0, str(_SAAS.parent))

from saas.inference.pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
