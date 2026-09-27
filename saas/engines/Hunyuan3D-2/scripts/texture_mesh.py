#!/usr/bin/env python3
"""Hunyuan3D-Paint: reference image + mesh → textured GLB.

Uses multiview appearance diffusion (turbo by default) instead of
sequential MV-Adapter bake. Tuned for ~20GB GPUs.

Props: QEM-decimate to 5k–15k tris before UV unwrap.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _ensure_local_weights(repo_id: str, subfolder: str, dest: Path) -> Path:
    """Download delight + paint subfolders into dest if missing."""
    delight = dest / "hunyuan3d-delight-v2-0"
    paint = dest / subfolder
    if delight.is_dir() and paint.is_dir():
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    import huggingface_hub

    print(f"[hunyuan-paint] downloading delight → {dest}", flush=True)
    huggingface_hub.snapshot_download(
        repo_id=repo_id,
        local_dir=str(dest),
        allow_patterns=["hunyuan3d-delight-v2-0/*"],
    )
    print(f"[hunyuan-paint] downloading {subfolder} → {dest}", flush=True)
    huggingface_hub.snapshot_download(
        repo_id=repo_id,
        local_dir=str(dest),
        allow_patterns=[f"{subfolder}/*"],
    )
    return dest


def _qem_decimate(mesh, face_count: int):
    """Inline QEM so this script does not depend on saas.inference imports."""
    target = int(max(5_000, min(15_000, int(face_count))))
    n = int(len(mesh.faces))
    if n <= target:
        print(f"[hunyuan-paint] QEM skip ({n} ≤ {target})", flush=True)
        return mesh
    print(f"[hunyuan-paint] QEM {n} → {target} faces (before UV)", flush=True)
    try:
        out = mesh.simplify_quadric_decimation(face_count=target)
    except TypeError:
        out = mesh.simplify_quadric_decimation(target)
    if out is None:
        raise RuntimeError("QEM decimation failed")
    print(f"[hunyuan-paint] QEM result faces={len(out.faces)}", flush=True)
    return out


def main() -> None:
    # Run from engine root so hy3dgen imports resolve
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import torch
    import trimesh
    from PIL import Image

    from hy3dgen.texgen import Hunyuan3DPaintPipeline
    from hy3dgen.texgen.differentiable_renderer.mesh_render import MeshRender

    p = argparse.ArgumentParser(description="Hunyuan3D-Paint mesh texturing")
    p.add_argument("--mesh", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--out", required=True, help="Output textured .glb")
    p.add_argument(
        "--model",
        default="tencent/Hunyuan3D-2",
        help="HF repo id or local snapshot root containing paint + delight",
    )
    p.add_argument(
        "--subfolder",
        default="hunyuan3d-paint-v2-0-turbo",
        choices=["hunyuan3d-paint-v2-0-turbo", "hunyuan3d-paint-v2-0"],
    )
    p.add_argument("--device", default="cuda")
    p.add_argument("--offload", action="store_true", help="CPU offload diffusion nets")
    p.add_argument("--render_size", type=int, default=1024)
    p.add_argument("--texture_size", type=int, default=1024)
    p.add_argument(
        "--asset_type",
        default="character",
        choices=["character", "prop"],
        help="prop → QEM to 5k–15k tris before UV",
    )
    p.add_argument(
        "--qem_faces",
        type=int,
        default=10_000,
        help="Prop QEM target faces (clamped to 5000–15000)",
    )
    args = p.parse_args()

    mesh_path = Path(args.mesh).resolve()
    image_path = Path(args.image).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not mesh_path.is_file():
        raise SystemExit(f"mesh not found: {mesh_path}")
    if not image_path.is_file():
        raise SystemExit(f"image not found: {image_path}")

    model = args.model
    model_path = Path(model)
    if model_path.is_dir():
        local = model_path
    else:
        weights_root = Path(os.environ.get("ANILAB_WEIGHTS", root.parents[2] / "weights"))
        local = weights_root / "hunyuan3d-2"
        local = _ensure_local_weights(model, args.subfolder, local)

    print(f"[hunyuan-paint] loading {local} / {args.subfolder}", flush=True)
    pipe = Hunyuan3DPaintPipeline.from_pretrained(str(local), subfolder=args.subfolder)

    # Shrink bake maps for 20GB cards (library defaults are 2048)
    pipe.config.render_size = args.render_size
    pipe.config.texture_size = args.texture_size
    pipe.render = MeshRender(
        default_resolution=args.render_size,
        texture_size=args.texture_size,
    )

    if args.offload:
        print("[hunyuan-paint] enable_model_cpu_offload", flush=True)
        pipe.enable_model_cpu_offload(device=args.device)

    mesh = trimesh.load(str(mesh_path), force="mesh", process=False)
    if isinstance(mesh, trimesh.Scene):
        geoms = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
        mesh = trimesh.util.concatenate(geoms) if geoms else mesh

    if args.asset_type == "prop":
        mesh = _qem_decimate(mesh, args.qem_faces)

    image = Image.open(image_path).convert("RGBA")
    print(
        f"[hunyuan-paint] texturing mesh={mesh_path.name} "
        f"asset_type={args.asset_type} faces={len(getattr(mesh, 'faces', []))} "
        f"render={args.render_size} tex={args.texture_size}",
        flush=True,
    )
    textured = pipe(mesh, image=image)
    textured.export(str(out_path))
    print(f"[hunyuan-paint] wrote {out_path}", flush=True)

    del pipe
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
