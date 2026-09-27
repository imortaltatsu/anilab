#!/usr/bin/env python3
"""CLI: `uv run main` / `python -m saas`."""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

SAAS = Path(__file__).resolve().parent
ROOT = SAAS.parent
BACKEND = SAAS / "backend"
FRONTEND = SAAS / "frontend"


def _backend_python() -> Path:
    venv_py = BACKEND / ".venv" / "bin" / "python"
    if venv_py.is_file():
        return venv_py
    return Path(sys.executable)


def main() -> None:
    parser = argparse.ArgumentParser(description="AniLab SaaS — game-ready image→3D")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Auto-reload API (dev)")
    parser.add_argument(
        "--with-frontend",
        action="store_true",
        help="Also start Vite on :5173 (requires bun or npm)",
    )
    args = parser.parse_args()

    py = _backend_python()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONUNBUFFERED"] = "1"

    api_cmd = [
        str(py),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        api_cmd.append("--reload")

    procs: list[subprocess.Popen] = []

    def _shutdown(*_: object) -> None:
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"AniLab API → http://{args.host}:{args.port}", flush=True)
    print("Pipeline: TripoSG → MV-Adapter → UniRig", flush=True)
    procs.append(subprocess.Popen(api_cmd, cwd=str(BACKEND), env=env))

    if args.with_frontend:
        bun = shutil.which("bun")
        npm = shutil.which("npm")
        if bun:
            fe_cmd = [bun, "run", "dev"]
        elif npm:
            fe_cmd = [npm, "run", "dev"]
        else:
            print("No bun/npm found; skipping frontend", flush=True)
            fe_cmd = None
        if fe_cmd:
            print("Frontend → http://127.0.0.1:5173", flush=True)
            procs.append(subprocess.Popen(fe_cmd, cwd=str(FRONTEND), env=env))

    code = procs[0].wait()
    for p in procs[1:]:
        if p.poll() is None:
            p.send_signal(signal.SIGTERM)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
