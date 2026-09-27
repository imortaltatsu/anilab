#!/usr/bin/env python3
"""Thin wrapper so `python main.py` and `uv run main` both work."""
from saas.cli import main

if __name__ == "__main__":
    main()
