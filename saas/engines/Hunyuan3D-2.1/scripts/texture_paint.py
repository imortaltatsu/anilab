#!/usr/bin/env python3
"""Hunyuan3D-2.1 Paint-only: reference image + mesh → PBR textured GLB.

Runs hy3dpaint (MaterialMVP / RomanTex) without the shape DiT.
Tuned for ~20GB GPUs: resolution=512, 6 views, optional mmgp offload.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    paint = root / "hy3dpaint"
    os.chdir(paint)
    # Imports expect cwd=hy3dpaint and sibling packages on path
    sys.path.insert(0, str(paint))
    sys.path.insert(0, str(root))

    # Torch CUDA libs for custom_rasterizer_kernel
    try:
        import torch

        torch_lib = Path(torch.__file__).resolve().parent / "lib"
        os.environ["LD_LIBRARY_PATH"] = (
            str(torch_lib) + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
        )
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Hunyuan3D-2.1 Paint-only texturing")
    p.add_argument("--mesh", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--out", required=True, help="Output textured .glb")
    p.add_argument(
        "--weights",
        default="",
        help="Local dir containing hunyuan3d-paintpbr-v2-1/ (or HF cache root)",
    )
    p.add_argument("--max_num_view", type=int, default=6)
    p.add_argument("--resolution", type=int, default=512, choices=[512, 768])
    p.add_argument("--render_size", type=int, default=1024)
    p.add_argument("--texture_size", type=int, default=2048)
    p.add_argument("--no_remesh", action="store_true", help="Skip InstantMeshes remesh")
    p.add_argument(
        "--mmgp",
        action="store_true",
        help="mmgp LowRAM_LowVRAM + 8-bit quant for ~20GB cards",
    )
    p.add_argument("--device", default="cuda")
    args = p.parse_args()

    mesh_path = Path(args.mesh).resolve()
    image_path = Path(args.image).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not mesh_path.is_file():
        raise SystemExit(f"mesh not found: {mesh_path}")
    if not image_path.is_file():
        raise SystemExit(f"image not found: {image_path}")

    weights_root = Path(
        args.weights
        or os.environ.get("ANILAB_WEIGHTS", root.parents[2] / "weights")
        / "hunyuan3d-2.1"
    ).resolve()
    paint_dir = weights_root / "hunyuan3d-paintpbr-v2-1"
    if not paint_dir.is_dir():
        # Accept weights_root itself being the paint folder
        if (weights_root / "model_index.json").is_file():
            paint_dir = weights_root
            weights_root = weights_root.parent
        else:
            raise SystemExit(
                f"paint weights missing: {paint_dir}\n"
                "Download: hf download tencent/Hunyuan3D-2.1 "
                "--include 'hunyuan3d-paintpbr-v2-1/**' "
                f"--local-dir {weights_root}"
            )

    # RealESRGAN next to hy3dpaint
    realesrgan = paint / "ckpt" / "RealESRGAN_x4plus.pth"
    if not realesrgan.is_file():
        raise SystemExit(f"RealESRGAN missing: {realesrgan}")

    from textureGenPipeline import Hunyuan3DPaintConfig, Hunyuan3DPaintPipeline

    conf = Hunyuan3DPaintConfig(args.max_num_view, args.resolution)
    conf.device = "cpu" if args.mmgp else args.device
    conf.multiview_cfg_path = str(paint / "cfgs" / "hunyuan-paint-pbr.yaml")
    conf.custom_pipeline = str(paint / "hunyuanpaintpbr")
    # multiview_utils joins this with hunyuan3d-paintpbr-v2-1/
    conf.multiview_pretrained_path = str(weights_root)
    conf.realesrgan_ckpt_path = str(realesrgan)
    conf.render_size = int(args.render_size)
    conf.texture_size = int(args.texture_size)
    # Prefer local DINO if present; else HF id
    dino_local = Path(os.environ.get("ANILAB_WEIGHTS", root.parents[2] / "weights")) / "dinov2-giant"
    conf.dino_ckpt_path = str(dino_local) if dino_local.is_dir() else "facebook/dinov2-giant"

    # Point huggingface snapshot_download at local by monkeypatching path resolution
    import huggingface_hub

    _orig_snap = huggingface_hub.snapshot_download

    def _local_snap(repo_id=None, **kwargs):
        allow = kwargs.get("allow_patterns") or []
        if repo_id in ("tencent/Hunyuan3D-2.1", str(weights_root)) or any(
            "paintpbr" in str(a) for a in allow
        ):
            has_w = paint_dir.is_dir() and (
                any(paint_dir.rglob("*.safetensors"))
                or any(paint_dir.rglob("*.bin"))
            )
            if has_w:
                print(f"[hy3d21-paint] using local weights {paint_dir}", flush=True)
                return str(weights_root)
        return _orig_snap(repo_id=repo_id, **kwargs)

    huggingface_hub.snapshot_download = _local_snap

    print(
        f"[hy3d21-paint] mesh={mesh_path.name} views={args.max_num_view} "
        f"res={args.resolution} render={args.render_size} tex={args.texture_size} "
        f"mmgp={args.mmgp}",
        flush=True,
    )
    pipe = Hunyuan3DPaintPipeline(conf)

    if args.mmgp:
        try:
            from mmgp import offload, profile_type

            core = pipe.models["multiview_model"].pipeline
            offload.profile(core, profile_type.LowRAM_LowVRAM)
            print("[hy3d21-paint] mmgp LowRAM_LowVRAM enabled", flush=True)
        except Exception as exc:
            print(f"[hy3d21-paint] mmgp soft-fail: {exc}", flush=True)

    # Pipeline writes .obj then converts to .glb beside it; force our out path
    tmp_obj = out_path.with_suffix(".obj")
    result = pipe(
        mesh_path=str(mesh_path),
        image_path=str(image_path),
        output_mesh_path=str(tmp_obj),
        use_remesh=not args.no_remesh,
        save_glb=True,
    )
    # Prefer converted glb next to obj
    produced = Path(str(result)).with_suffix(".glb") if result else tmp_obj.with_suffix(".glb")
    if not produced.is_file():
        produced = tmp_obj.with_suffix(".glb")
    if produced.is_file() and produced.resolve() != out_path.resolve():
        import shutil

        shutil.copy2(produced, out_path)
    if not out_path.is_file():
        raise SystemExit(f"paint failed — missing {out_path}")
    print(f"[hy3d21-paint] wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
