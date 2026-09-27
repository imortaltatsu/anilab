#!/usr/bin/env python3
"""Persistent warm daemon for UniRig automated humanoid rigging and skinning.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent


class UniRigService:
    def __init__(self, port: int = 8103):
        self.port = port
        self.engine_root = ENGINE_ROOT
        print(f"[UniRig Daemon] WARM & READY on port {port}", flush=True)

    def rig(self, input_mesh: str, output_mesh: str, seed: int = 42, faces: int = 35_000):
        t0 = time.perf_counter()
        out_dir = Path(output_mesh).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        name = Path(output_mesh).stem

        skeleton = out_dir / f"{name}_skeleton.fbx"
        skin = out_dir / f"{name}_skin.fbx"

        env = os.environ.copy()
        bin_dir = str(self.engine_root / ".venv" / "bin")
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["VIRTUAL_ENV"] = str(self.engine_root / ".venv")
        env["PYTHONUNBUFFERED"] = "1"

        # 1. Skeleton prediction
        print(f"[UniRig Daemon] Generating skeleton for {input_mesh}...", flush=True)
        cmd1 = [
            "bash",
            "launch/inference/generate_skeleton.sh",
            "--input", str(input_mesh),
            "--output", str(skeleton),
            "--seed", str(seed),
            "--faces_target_count", str(faces),
            "--force_override", "true",
        ]
        p1 = subprocess.run(cmd1, cwd=str(self.engine_root), env=env)
        if p1.returncode != 0 or not skeleton.is_file():
            raise RuntimeError(f"Skeleton prediction failed ({p1.returncode})")

        # 2. Smooth skinning
        print(f"[UniRig Daemon] Generating skin weights...", flush=True)
        cmd2 = [
            "bash",
            "launch/inference/generate_skin.sh",
            "--input", str(skeleton),
            "--output", str(skin),
            "--seed", str(seed),
            "--force_override", "true",
        ]
        p2 = subprocess.run(cmd2, cwd=str(self.engine_root), env=env)
        if p2.returncode != 0 or not skin.is_file():
            raise RuntimeError(f"Skin generation failed ({p2.returncode})")

        # 3. Merge weights into rigged GLB
        print(f"[UniRig Daemon] Merging into {output_mesh}...", flush=True)
        cmd3 = [
            "bash",
            "launch/inference/merge.sh",
            "--source", str(skin),
            "--target", str(input_mesh),
            "--output", str(output_mesh),
        ]
        p3 = subprocess.run(cmd3, cwd=str(self.engine_root), env=env)
        if not Path(output_mesh).is_file():
            raise RuntimeError(f"Merge to GLB failed: {output_mesh}")

        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[UniRig Daemon] Auto-rig completed in {elapsed}s → {output_mesh}", flush=True)
        return {"status": "ok", "output_mesh": output_mesh, "elapsed_s": elapsed}


def make_handler(service: UniRigService):
    class DaemonHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                res = json.dumps({
                    "status": "ready",
                    "engine": "unirig",
                    "port": service.port,
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res)))
                self.end_headers()
                self.wfile.write(res)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/rig":
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    result = service.rig(
                        input_mesh=body["input_mesh"],
                        output_mesh=body["output_mesh"],
                        seed=body.get("seed", 42),
                        faces=body.get("faces", 35_000),
                    )
                    res = json.dumps(result).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(res)))
                    self.end_headers()
                    self.wfile.write(res)
                except Exception as exc:
                    err = json.dumps({"status": "error", "detail": str(exc)}).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
            else:
                self.send_response(404)
                self.end_headers()

    return DaemonHandler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8103)
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

    service = UniRigService(port=args.port)
    server = HTTPServer(("127.0.0.1", args.port), make_handler(service))
    print(f"[UniRig Daemon] Listening on http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
