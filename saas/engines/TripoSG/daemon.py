#!/usr/bin/env python3
"""Persistent warm daemon for TripoSG shape generation.
Keeps model weights permanently loaded in VRAM for zero cold-start latency.
"""
import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Union

import numpy as np
import torch
import trimesh
from PIL import Image

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

from briarmbg import BriaRMBG
from image_process import prepare_image
from triposg.pipelines.pipeline_triposg import TripoSGPipeline
import pymeshlab


def mesh_to_pymesh(vertices, faces):
    mesh = pymeshlab.Mesh(vertex_matrix=vertices, face_matrix=faces)
    ms = pymeshlab.MeshSet()
    ms.add_mesh(mesh)
    return ms


def pymesh_to_trimesh(mesh):
    verts = mesh.vertex_matrix()
    faces = mesh.face_matrix()
    return trimesh.Trimesh(vertices=verts, faces=faces)


def simplify_mesh(mesh: trimesh.Trimesh, n_faces: int):
    if n_faces > 0 and mesh.faces.shape[0] > n_faces:
        ms = mesh_to_pymesh(mesh.vertices, mesh.faces)
        ms.meshing_merge_close_vertices()
        ms.meshing_decimation_quadric_edge_collapse(targetfacenum=n_faces)
        return pymesh_to_trimesh(ms.current_mesh())
    return mesh


@torch.no_grad()
def run_triposg(
    pipe: Any,
    image_input: Union[str, Image.Image],
    rmbg_net: Any,
    seed: int,
    num_inference_steps: int = 50,
    guidance_scale: float = 7.0,
    faces: int = -1,
) -> trimesh.Trimesh:
    img_pil = prepare_image(image_input, bg_color=np.array([1.0, 1.0, 1.0]), rmbg_net=rmbg_net)
    outputs = pipe(
        image=img_pil,
        generator=torch.Generator(device=pipe.device).manual_seed(seed),
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
    ).samples[0]
    mesh = trimesh.Trimesh(outputs[0].astype(np.float32), np.ascontiguousarray(outputs[1]))
    if faces > 0:
        mesh = simplify_mesh(mesh, faces)
    return mesh


class TripoSGService:
    def __init__(self, device: str = "cuda", port: int = 8101):
        self.device = device
        self.dtype = torch.float16
        self.port = port
        self.engine_root = Path(__file__).resolve().parent

        weights_dir = self.engine_root / "pretrained_weights" / "TripoSG"
        rmbg_dir = self.engine_root / "pretrained_weights" / "RMBG-1.4"

        print(f"[TripoSG Daemon] Loading warm models onto {device}...", flush=True)
        t0 = time.perf_counter()

        self.rmbg_net = BriaRMBG.from_pretrained(str(rmbg_dir)).to(device)
        self.rmbg_net.eval()

        self.pipe = TripoSGPipeline.from_pretrained(str(weights_dir)).to(device, self.dtype)

        warm_time = round(time.perf_counter() - t0, 2)
        vram_mb = round(torch.cuda.memory_allocated(device) / (1024 * 1024), 1) if torch.cuda.is_available() else 0
        print(f"[TripoSG Daemon] WARM & READY in {warm_time}s! VRAM allocated: {vram_mb} MB on port {port}", flush=True)

    def generate(self, image_input: str, output_path: str, seed: int = 42, faces: int = 35_000, steps: int = 50):
        t0 = time.perf_counter()
        mesh = run_triposg(
            self.pipe,
            image_input=image_input,
            rmbg_net=self.rmbg_net,
            seed=seed,
            num_inference_steps=steps,
            guidance_scale=7.0,
            faces=faces,
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        mesh.export(output_path)
        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[TripoSG Daemon] Generated {output_path} ({len(mesh.faces)} faces) in {elapsed}s", flush=True)
        return {"status": "ok", "output_path": output_path, "faces": len(mesh.faces), "elapsed_s": elapsed}


def make_handler(service: TripoSGService):
    class DaemonHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress default noisy access logs

        def do_GET(self):
            if self.path == "/health":
                vram_mb = round(torch.cuda.memory_allocated(service.device) / (1024 * 1024), 1) if torch.cuda.is_available() else 0
                res = json.dumps({
                    "status": "ready",
                    "engine": "triposg",
                    "device": service.device,
                    "vram_mb": vram_mb,
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
            if self.path == "/generate":
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    image_input = body["image_input"]
                    output_path = body["output_path"]
                    seed = body.get("seed", 42)
                    faces = body.get("faces", 35_000)
                    steps = body.get("steps", 50)

                    result = service.generate(
                        image_input=image_input,
                        output_path=output_path,
                        seed=seed,
                        faces=faces,
                        steps=steps,
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
    parser.add_argument("--port", type=int, default=8101)
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

    service = TripoSGService(device=args.device, port=args.port)
    server = HTTPServer(("127.0.0.1", args.port), make_handler(service))
    print(f"[TripoSG Daemon] Listening on http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
