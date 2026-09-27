import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import argparse
import gc
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import torch
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mvadapter.pipelines.pipeline_texture import ModProcessConfig, TexturePipeline
from mvadapter.utils import make_image_grid
from mvadapter.utils.mesh_utils.mesh_process import process_raw
from scripts.inference_ig2mv_sdxl import prepare_pipeline, remove_bg, run_pipeline

_AZIMUTH = [0, 90, 180, 270, 180, 180]
_ELEVATION = [0, 0, 0, 0, 89.99, -89.99]
_CAMERA_DISTANCE = 1.8


class MVAdapterService:
    def __init__(self, device: str = "cuda", port: int = 8102):
        self.device = device
        self.port = port
        self.engine_root = Path(__file__).resolve().parent

        print(f"[MV-Adapter Daemon] Initializing warm texturing models on {device}...", flush=True)
        t0 = time.perf_counter()

        self.pipe = prepare_pipeline(
            base_model="stabilityai/stable-diffusion-xl-base-1.0",
            vae_model="madebyollin/sdxl-vae-fp16-fix",
            unet_model=None,
            lora_model=None,
            adapter_path="huanngzh/mv-adapter",
            scheduler=None,
            num_views=6,
            device=device,
            dtype=torch.float16,
        )

        # Keep segmentation model on CPU until needed (~2GB VRAM saved)
        self.birefnet = AutoModelForImageSegmentation.from_pretrained(
            "ZhengPeng7/BiRefNet", trust_remote_code=True
        ).eval()

        self.transform_image = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        # Initialize TexturePipeline and offload upscaler + inpainter to CPU until projection
        self.texture_pipe = TexturePipeline(
            upscaler_ckpt_path=str(self.engine_root / "checkpoints" / "RealESRGAN_x2plus.pth"),
            inpaint_ckpt_path=str(self.engine_root / "checkpoints" / "big-lama.pt"),
            device=device,
        )
        self.texture_pipe.to_device("cpu")

        warm_time = round(time.perf_counter() - t0, 2)
        vram_mb = round(torch.cuda.memory_allocated(device) / (1024 * 1024), 1) if torch.cuda.is_available() else 0
        print(f"[MV-Adapter Daemon] WARM & READY in {warm_time}s! VRAM allocated: {vram_mb} MB on port {port}", flush=True)

    def remove_bg_fn(self, x):
        # Dynamically stage BiRefNet to GPU for the 0.5s segmentation, then offload
        self.birefnet.to(self.device)
        res = remove_bg(x, self.birefnet, self.transform_image, self.device)
        self.birefnet.to("cpu")
        torch.cuda.empty_cache()
        return res

    def texture(
        self,
        mesh: str,
        image: str,
        save_dir: str,
        save_name: str,
        text: str = "high quality",
        seed: int = 42,
        num_inference_steps: int = 50,
        guidance_scale: float = 4.0,
        uv_size: int = 2048,
        preprocess_mesh: bool = True,
        remove_bg: bool = True,
        rotation_yaw: float = 0.0,
        rotation_pitch: float = 0.0,
        inpaint_mode: str = "uv",
    ):
        t0 = time.perf_counter()
        os.makedirs(save_dir, exist_ok=True)

        # 1. Unwrap UV
        file_suffix = os.path.splitext(mesh)[-1]
        mesh_unwarp = mesh.replace(file_suffix, f"_unwarp{file_suffix}")
        print(f"[MV-Adapter Daemon] UV unwrap → {mesh_unwarp}")
        process_raw(mesh, mesh_unwarp, preprocess=preprocess_mesh, device="cpu", uv_size=uv_size)

        # 2. Multiview generation using warm SDXL pipe
        bg_fn = self.remove_bg_fn if remove_bg else None
        images, _, _, _ = run_pipeline(
            self.pipe,
            mesh_path=mesh_unwarp,
            num_views=6,
            text=text,
            image=image,
            height=768,
            width=768,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            seed=seed,
            reference_conditioning_scale=1.0,
            negative_prompt="watermark, logo, text, ugly, deformed, noisy, blurry, low contrast, extra limbs, missing limbs, cropped",
            device=self.device,
            remove_bg_fn=bg_fn,
        )
        mv_path = os.path.join(save_dir, f"{save_name}.png")
        make_image_grid(images, rows=1).save(mv_path)

        # 3. Texture projection (stage models to GPU, run bake, then offload back to CPU)
        torch.cuda.empty_cache()
        gc.collect()
        self.texture_pipe.to_device(self.device)
        try:
            self.texture_pipe(
                mesh_path=mesh_unwarp,
                save_dir=save_dir,
                save_name=save_name,
                uv_unwarp=False,
                preprocess_mesh=False,
                uv_size=uv_size,
                rgb_path=mv_path,
                rgb_process_config=ModProcessConfig(
                    view_upscale=True,
                    inpaint_mode=inpaint_mode,
                    view_inpaint_min_rounds=1,
                    view_inpaint_max_rounds=2,
                ),
                camera_azimuth_deg=[float((az + rotation_yaw) % 360) for az in _AZIMUTH],
                camera_elevation_deg=[float(el + rotation_pitch) for el in _ELEVATION],
                camera_distance=_CAMERA_DISTANCE,
                camera_ortho_scale=1.1,
                uv_inpaint_use_network=True,
                poisson_reprojection=False,
            )
        finally:
            self.texture_pipe.to_device("cpu")
            torch.cuda.empty_cache()
            gc.collect()

        shaded = os.path.join(save_dir, f"{save_name}_shaded.glb")
        if not os.path.isfile(shaded):
            nested = os.path.join(save_dir, f"{save_name}_shaded", f"{save_name}_shaded.glb")
            if os.path.isfile(nested):
                import shutil
                shutil.copy2(nested, shaded)

        elapsed = round(time.perf_counter() - t0, 2)
        print(f"[MV-Adapter Daemon] Texturing completed in {elapsed}s → {shaded}", flush=True)
        return {"status": "ok", "mesh_out": shaded, "multiview": mv_path, "elapsed_s": elapsed}


def make_handler(service: MVAdapterService):
    class DaemonHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                vram_mb = round(torch.cuda.memory_allocated(service.device) / (1024 * 1024), 1) if torch.cuda.is_available() else 0
                res = json.dumps({
                    "status": "ready",
                    "engine": "mvadapter",
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
            if self.path == "/texture":
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    result = service.texture(
                        mesh=body["mesh"],
                        image=body["image"],
                        save_dir=body["save_dir"],
                        save_name=body["save_name"],
                        text=body.get("text", "high quality"),
                        seed=body.get("seed", 42),
                        num_inference_steps=body.get("num_inference_steps", 50),
                        guidance_scale=body.get("guidance_scale", 4.0),
                        uv_size=body.get("uv_size", 2048),
                        preprocess_mesh=body.get("preprocess_mesh", True),
                        remove_bg=body.get("remove_bg", True),
                        rotation_yaw=float(body.get("rotation_yaw", 0.0)),
                        rotation_pitch=float(body.get("rotation_pitch", 0.0)),
                        inpaint_mode=body.get("inpaint_mode", "uv"),
                    )
                    res = json.dumps(result).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(res)))
                    self.end_headers()
                    self.wfile.write(res)
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
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
    parser.add_argument("--port", type=int, default=8102)
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

    service = MVAdapterService(device=args.device, port=args.port)
    server = HTTPServer(("127.0.0.1", args.port), make_handler(service))
    print(f"[MV-Adapter Daemon] Listening on http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
