#!/usr/bin/env python3
"""Daemon manager: Start, stop, and monitor warm engine daemons across Dual GPUs."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from .daemon_client import (
    MVADAPTER_PORT,
    TRIPOSG_PORT,
    UNIRIG_PORT,
    is_daemon_ready,
)
from .paths import (
    MVADAPTER_PYTHON,
    MVADAPTER_ROOT,
    TRIPOSG_PYTHON,
    TRIPOSG_ROOT,
    UNIRIG_PYTHON,
    UNIRIG_ROOT,
)

PID_DIR = Path("/tmp/yeetgen_daemons")
PID_DIR.mkdir(parents=True, exist_ok=True)


def start_daemon(name: str, python: Path, script: Path, cwd: Path, port: int, gpu_id: int):
    if is_daemon_ready(port):
        print(f"[{name}] Already warm & responsive on port {port} (GPU {gpu_id})")
        return

    pid_file = PID_DIR / f"{name}.pid"
    log_file = PID_DIR / f"{name}.log"

    env = os.environ.copy()
    bin_dir = str(python.parent)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["VIRTUAL_ENV"] = str(python.parent.parent)
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    print(f"[{name}] Booting warm daemon on GPU {gpu_id}, port {port}...", flush=True)
    with open(log_file, "a") as log_f:
        proc = subprocess.Popen(
            [str(python), str(script), "--port", str(port), "--device", "cuda"],
            cwd=str(cwd),
            env=env,
            stdout=log_f,
            stderr=log_f,
            start_new_session=True,
        )

    pid_file.write_text(str(proc.pid))
    print(f"[{name}] Spawned PID {proc.pid}. Waiting for warm model initialization...", flush=True)

    # Poll until ready or failed
    t0 = time.time()
    while time.time() - t0 < 90:
        if is_daemon_ready(port):
            print(f"[{name}] ✓ Warm daemon READY on port {port} in {round(time.time() - t0, 1)}s!")
            return
        if proc.poll() is not None:
            print(f"[{name}] ✗ Daemon exited unexpectedly ({proc.returncode}). Check {log_file}")
            return
        time.sleep(1.0)
    print(f"[{name}] Warning: Initialization still running in background. Check {log_file}")


def stop_daemon(name: str):
    pid_file = PID_DIR / f"{name}.pid"
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 15)  # SIGTERM
            print(f"[{name}] Stopped daemon PID {pid}")
        except Exception:
            pass
        pid_file.unlink(missing_ok=True)


def check_status():
    print("\n=== YeetGen Warm Daemon Status ===")
    status_tripo = "✓ READY (Warm VRAM)" if is_daemon_ready(TRIPOSG_PORT) else "OFFLINE"
    status_mv = "✓ READY (Warm VRAM)" if is_daemon_ready(MVADAPTER_PORT) else "OFFLINE"
    status_unirig = "✓ READY (Warm VRAM)" if is_daemon_ready(UNIRIG_PORT) else "OFFLINE"

    print(f"1. TripoSG (Shape)    : Port {TRIPOSG_PORT} (GPU 0) → {status_tripo}")
    print(f"2. MV-Adapter (Texture): Port {MVADAPTER_PORT} (GPU 1) → {status_mv}")
    print(f"3. UniRig (Auto-Rig)  : Port {UNIRIG_PORT} (GPU 0) → {status_unirig}")
    print("==================================\n")


def main():
    parser = argparse.ArgumentParser(description="Manage YeetGen persistent warm daemons")
    parser.add_argument("action", choices=["start", "stop", "restart", "status"])
    parser.add_argument("--gpu-shape", type=int, default=0, help="GPU for TripoSG")
    parser.add_argument("--gpu-texture", type=int, default=1, help="GPU for MV-Adapter")
    parser.add_argument("--gpu-rig", type=int, default=0, help="GPU for UniRig")
    args = parser.parse_args()

    if args.action in ("stop", "restart"):
        stop_daemon("triposg")
        stop_daemon("mvadapter")
        stop_daemon("unirig")

    if args.action in ("start", "restart"):
        start_daemon("triposg", TRIPOSG_PYTHON, TRIPOSG_ROOT / "daemon.py", TRIPOSG_ROOT, TRIPOSG_PORT, args.gpu_shape)
        start_daemon("mvadapter", MVADAPTER_PYTHON, MVADAPTER_ROOT / "daemon.py", MVADAPTER_ROOT, MVADAPTER_PORT, args.gpu_texture)
        start_daemon("unirig", UNIRIG_PYTHON, UNIRIG_ROOT / "daemon.py", UNIRIG_ROOT, UNIRIG_PORT, args.gpu_rig)

    check_status()


if __name__ == "__main__":
    main()
