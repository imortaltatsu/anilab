#!/usr/bin/env python3
"""TripoSG (shape) → MV-Adapter Img2Texture → UniRig (skeleton + skin).

Produces a game-ready textured, skinned GLB.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .opts import OPTS
from .daemon_client import (
    triposg_warm_generate,
    mvadapter_warm_texture,
    unirig_warm_rig,
)
from .paths import (
    HUNYUAN3D_PYTHON,
    HUNYUAN3D_ROOT,
    HUNYUAN3D_WEIGHTS,
    HUNYUAN3D21_PYTHON,
    HUNYUAN3D21_ROOT,
    HUNYUAN3D21_WEIGHTS,
    MVADAPTER_PYTHON,
    MVADAPTER_ROOT,
    TRIPOSG_PYTHON,
    TRIPOSG_ROOT,
    UNIRIG_PYTHON,
    UNIRIG_ROOT,
    WEIGHTS,
    validate_engines,
)


@dataclass
class PipelineResult:
    mesh_glb: Path
    mesh_raw: Path
    mesh_textured: Path
    multiview: Path | None = None
    timings: dict = field(default_factory=dict)


def _run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    e = os.environ.copy()
    e["ANILAB_WEIGHTS"] = str(WEIGHTS)
    e["PYTHONUNBUFFERED"] = "1"
    # Piped logs (worker stdout) break tqdm ASCII bars with ncols=0 → ZeroDivisionError.
    e.pop("TQDM_ASCII", None)
    e["TQDM_NCOLS"] = e.get("TQDM_NCOLS") or "100"
    e["COLUMNS"] = e.get("COLUMNS") or "100"
    e["TERM"] = e.get("TERM") or "xterm-256color"
    e["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    if env:
        e.update(env)
        e.pop("TQDM_ASCII", None)
    proc = subprocess.run(cmd, cwd=str(cwd), env=e, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def _unirig_env() -> dict[str, str]:
    bin_dir = str(UNIRIG_ROOT / ".venv" / "bin")
    return {
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "VIRTUAL_ENV": str(UNIRIG_ROOT / ".venv"),
        "ANILAB_WEIGHTS": str(WEIGHTS),
        "TQDM_NCOLS": "100",
        "COLUMNS": "100",
        "TERM": "xterm-256color",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
    }


class GameReadyPipeline:
    """Orchestrates the three engine CLIs with their own virtualenvs."""

    def __init__(
        self,
        *,
        asset_type: str = OPTS.asset_type,
        faces: int = OPTS.shape_faces,
        triposg_steps: int = OPTS.shape_steps,
        texture_backend: str = OPTS.texture_backend,
        texture_text: str = OPTS.texture_text,
        texture_steps: int = OPTS.texture_steps,
        texture_guidance: float = OPTS.texture_guidance,
        texture_uv_size: int = OPTS.texture_uv_size,
        texture_render_size: int = 1024,
        texture_offload: bool = True,
        texture_subfolder: str = "hunyuan3d-paint-v2-0-turbo",
        texture_preprocess_mesh: bool = OPTS.texture_preprocess_mesh,
        seed: int = OPTS.seed,
        device: str = OPTS.device,
        rotation_yaw: float = 0.0,
        rotation_pitch: float = 0.0,
        inpaint_mode: str = "uv",
    ) -> None:
        self.asset_type = (asset_type or "character").strip().lower()
        self.texture_backend = (texture_backend or OPTS.texture_backend or "hy3d21").strip().lower()
        validate_engines(texture_backend=self.texture_backend)
        self.faces = faces
        self.triposg_steps = triposg_steps
        self.texture_text = texture_text
        self.texture_steps = texture_steps
        self.texture_guidance = texture_guidance
        self.texture_uv_size = texture_uv_size
        self.texture_render_size = texture_render_size
        self.texture_offload = texture_offload
        self.texture_subfolder = texture_subfolder
        self.texture_preprocess_mesh = texture_preprocess_mesh
        self.seed = seed
        self.device = device
        self.rotation_yaw = rotation_yaw
        self.rotation_pitch = rotation_pitch
        self.inpaint_mode = inpaint_mode

    @property
    def is_prop(self) -> bool:
        return self.asset_type in ("prop", "props", "object", "item")

    def run(self, image_path: Path, output_dir: Path, name: str = "asset") -> PipelineResult:
        image_path = image_path.resolve()
        if not image_path.is_file():
            raise FileNotFoundError(image_path)

        out = output_dir.resolve()
        out.mkdir(parents=True, exist_ok=True)
        timings: dict = {
            "image": str(image_path),
            "faces": self.faces,
            "seed": self.seed,
            "asset_type": self.asset_type,
            "texture_backend": self.texture_backend,
        }

        mesh_raw = out / "mesh_raw.glb"
        mv_png = out / f"{name}_i2tex.png"
        mesh_tex = out / f"{name}_textured.glb"
        rigged = out / "mesh.glb"

        t0 = time.perf_counter()
        resume_raw = os.environ.get("ANILAB_RESUME_MESH_RAW")
        if resume_raw and Path(resume_raw).is_file():
            if Path(resume_raw).resolve() != mesh_raw.resolve():
                shutil.copy2(resume_raw, mesh_raw)
            print(f"[resume] skip TripoSG, using {mesh_raw}", flush=True)
            timings["triposg_s"] = 0.0
            timings["triposg_skipped"] = True
        elif mesh_raw.is_file() and os.environ.get("ANILAB_SKIP_TRIPOSG") == "1":
            print(f"[resume] skip TripoSG, existing {mesh_raw}", flush=True)
            timings["triposg_s"] = 0.0
            timings["triposg_skipped"] = True
        else:
            self._triposg(image_path, mesh_raw)
            timings["triposg_s"] = round(time.perf_counter() - t0, 3)

        t1 = time.perf_counter()
        mesh_tex = self._texture(image_path, mesh_raw, out, name)
        if (out / f"{name}_i2tex.png").is_file():
            mv_png = out / f"{name}_i2tex.png"
        timings["texture_s"] = round(time.perf_counter() - t1, 3)
        timings["mvadapter_s"] = timings["texture_s"]

        t2 = time.perf_counter()
        if self.is_prop:
            shutil.copy2(mesh_tex, rigged)
            timings["unirig_s"] = 0.0
            timings["unirig_skipped"] = True
            print(f"[prop] skip UniRig → {rigged}", flush=True)
        else:
            self._unirig(mesh_tex, out, name, rigged)
            timings["unirig_s"] = round(time.perf_counter() - t2, 3)
        timings["total_s"] = round(time.perf_counter() - t0, 3)
        timings["output"] = str(rigged)

        (out / "pipeline_timing.json").write_text(json.dumps(timings, indent=2))
        print(json.dumps(timings, indent=2), flush=True)
        print(f"Done → {rigged}", flush=True)

        return PipelineResult(
            mesh_glb=rigged,
            mesh_raw=mesh_raw,
            mesh_textured=mesh_tex,
            multiview=mv_png if mv_png.is_file() else None,
            timings=timings,
        )

    def run_rig(self, mesh_path: Path, output_dir: Path, name: str = "asset") -> PipelineResult:
        """UniRig only: textured/static mesh → skinned GLB."""
        mesh_path = mesh_path.resolve()
        if not mesh_path.is_file():
            raise FileNotFoundError(mesh_path)

        out = output_dir.resolve()
        out.mkdir(parents=True, exist_ok=True)
        mesh_tex = out / f"input{mesh_path.suffix.lower() or '.glb'}"
        if mesh_path != mesh_tex:
            shutil.copy2(mesh_path, mesh_tex)
        rigged = out / "mesh.glb"
        timings: dict = {"mesh": str(mesh_path), "faces": self.faces, "seed": self.seed, "mode": "rig"}

        t0 = time.perf_counter()
        self._unirig(mesh_tex, out, name, rigged)
        timings["unirig_s"] = round(time.perf_counter() - t0, 3)
        timings["total_s"] = timings["unirig_s"]
        timings["output"] = str(rigged)
        (out / "pipeline_timing.json").write_text(json.dumps(timings, indent=2))
        print(json.dumps(timings, indent=2), flush=True)
        print(f"Done → {rigged}", flush=True)
        return PipelineResult(
            mesh_glb=rigged,
            mesh_raw=mesh_tex,
            mesh_textured=mesh_tex,
            timings=timings,
        )

    def _triposg(self, image: Path, mesh_out: Path) -> None:
        # Check if warm TripoSG daemon is online
        if triposg_warm_generate(image, mesh_out, self.seed, self.faces, self.triposg_steps):
            return

        # Use TripoSG's own inference script (loads weights into engine dir).
        env = {
            "PYTHONPATH": str(TRIPOSG_ROOT)
            + os.pathsep
            + str(TRIPOSG_ROOT / "scripts")
            + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
        }
        _run(
            [
                str(TRIPOSG_PYTHON),
                str(TRIPOSG_ROOT / "scripts" / "inference_triposg.py"),
                "--image-input",
                str(image),
                "--output-path",
                str(mesh_out),
                "--seed",
                str(self.seed),
                "--num-inference-steps",
                str(self.triposg_steps),
                "--faces",
                str(self.faces),
            ],
            cwd=TRIPOSG_ROOT,
            env=env,
            timeout=60 * 30,
        )
        if not mesh_out.is_file():
            raise FileNotFoundError(mesh_out)

    def _texture(self, image: Path, mesh: Path, save_dir: Path, save_name: str) -> Path:
        backend = self.texture_backend
        if backend in ("hy3d21", "hunyuan21", "paint21", "hy3dpaint"):
            return self._hy3d21(image, mesh, save_dir, save_name)
        if backend in ("hunyuan", "hunyuan3d", "paint"):
            return self._hunyuan(image, mesh, save_dir, save_name)
        if backend in ("mvadapter", "mv", "legacy"):
            return self._mvadapter(image, mesh, save_dir, save_name)
        raise ValueError(
            f"Unknown texture_backend={backend!r} (use hy3d21|hunyuan|mvadapter)"
        )

    def _hy3d21(self, image: Path, mesh: Path, save_dir: Path, save_name: str) -> Path:
        """Hunyuan3D-2.1 Paint-only (PBR) on an existing TripoSG mesh."""
        out_glb = save_dir / f"{save_name}_textured.glb"
        legacy_alias = save_dir / f"{save_name}_i2tex_shaded.glb"
        hy_bin = str(HUNYUAN3D21_ROOT / ".venv" / "bin")
        # custom_rasterizer needs torch's libc10.so on LD_LIBRARY_PATH
        torch_lib = next(
            (HUNYUAN3D21_ROOT / ".venv").glob("lib/python*/site-packages/torch/lib"),
            None,
        )
        ld = os.environ.get("LD_LIBRARY_PATH", "")
        if torch_lib and torch_lib.is_dir():
            ld = f"{torch_lib}{os.pathsep}{ld}" if ld else str(torch_lib)
        env = {
            "PATH": f"{hy_bin}:{os.environ.get('PATH', '')}",
            "VIRTUAL_ENV": str(HUNYUAN3D21_ROOT / ".venv"),
            "ANILAB_WEIGHTS": str(WEIGHTS),
            "HF_HUB_ENABLE_HF_TRANSFER": "0",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
            "LD_LIBRARY_PATH": ld,
            "PYTHONPATH": str(HUNYUAN3D21_ROOT / "hy3dpaint")
            + os.pathsep
            + str(HUNYUAN3D21_ROOT)
            + (
                os.pathsep + os.environ["PYTHONPATH"]
                if os.environ.get("PYTHONPATH")
                else ""
            ),
        }
        cmd = [
            str(HUNYUAN3D21_PYTHON),
            str(HUNYUAN3D21_ROOT / "scripts" / "texture_paint.py"),
            "--mesh",
            str(mesh),
            "--image",
            str(image),
            "--out",
            str(out_glb),
            "--weights",
            str(HUNYUAN3D21_WEIGHTS),
            "--max_num_view",
            "6",
            "--resolution",
            "512",
            "--render_size",
            str(min(self.texture_render_size, 1024)),
            "--texture_size",
            str(min(self.texture_uv_size, 2048)),
            "--device",
            self.device,
            "--mmgp",  # required on ~20GB Ada for paint-only
        ]
        _run(cmd, cwd=HUNYUAN3D21_ROOT / "hy3dpaint", env=env, timeout=60 * 60)
        if not out_glb.is_file():
            raise FileNotFoundError(f"hy3d21 textured mesh missing: {out_glb}")
        if out_glb.resolve() != legacy_alias.resolve():
            shutil.copy2(out_glb, legacy_alias)
        return out_glb

    def _hunyuan(self, image: Path, mesh: Path, save_dir: Path, save_name: str) -> Path:
        out_glb = save_dir / f"{save_name}_textured.glb"
        # Alias kept for worker resume paths that look for *_i2tex_shaded.glb
        legacy_alias = save_dir / f"{save_name}_i2tex_shaded.glb"
        hy_bin = str(HUNYUAN3D_ROOT / ".venv" / "bin")
        model = str(HUNYUAN3D_WEIGHTS) if HUNYUAN3D_WEIGHTS.is_dir() else "tencent/Hunyuan3D-2"
        env = {
            "PATH": f"{hy_bin}:{os.environ.get('PATH', '')}",
            "VIRTUAL_ENV": str(HUNYUAN3D_ROOT / ".venv"),
            "ANILAB_WEIGHTS": str(WEIGHTS),
            "PYTHONPATH": str(HUNYUAN3D_ROOT)
            + (
                os.pathsep + os.environ["PYTHONPATH"]
                if os.environ.get("PYTHONPATH")
                else ""
            ),
        }
        cmd = [
            str(HUNYUAN3D_PYTHON),
            str(HUNYUAN3D_ROOT / "scripts" / "texture_mesh.py"),
            "--mesh",
            str(mesh),
            "--image",
            str(image),
            "--out",
            str(out_glb),
            "--model",
            model,
            "--subfolder",
            self.texture_subfolder,
            "--device",
            self.device,
            "--render_size",
            str(self.texture_render_size),
            "--texture_size",
            str(self.texture_uv_size),
            "--asset_type",
            "prop" if self.is_prop else "character",
        ]
        if self.texture_offload:
            cmd.append("--offload")
        _run(cmd, cwd=HUNYUAN3D_ROOT, env=env, timeout=60 * 45)
        if not out_glb.is_file():
            raise FileNotFoundError(f"Hunyuan textured mesh missing: {out_glb}")
        if out_glb.resolve() != legacy_alias.resolve():
            shutil.copy2(out_glb, legacy_alias)
        return out_glb

    def _mvadapter(self, image: Path, mesh: Path, save_dir: Path, save_name: str) -> Path:
        """1:1 with saas/storage/outputs/bench_image (bench_image_i2tex.png).

        Exact CLI recipe::
            -m scripts.texture_i2tex --variant sdxl --text high quality
            --preprocess_mesh --remove_bg
            (+ steps / guidance / uv_size from OPTS when set)
        """
        # Check if warm MV-Adapter daemon is online
        warm_out = mvadapter_warm_texture(
            mesh=mesh,
            image=image,
            save_dir=save_dir,
            save_name=f"{save_name}_i2tex",
            text=self.texture_text or "high quality",
            seed=self.seed,
            steps=self.texture_steps,
            guidance=self.texture_guidance,
            uv_size=self.texture_uv_size,
            preprocess_mesh=True,
            remove_bg=True,
            rotation_yaw=self.rotation_yaw,
            rotation_pitch=self.rotation_pitch,
            inpaint_mode=self.inpaint_mode,
        )
        if warm_out is not None and warm_out.is_file():
            canonical = save_dir / f"{save_name}_textured.glb"
            if warm_out.resolve() != canonical.resolve():
                shutil.copy2(warm_out, canonical)
            return warm_out

        # If warm daemon was not used or failed, ensure daemon is stopped to free GPU 1 VRAM
        from .daemon_manager import stop_daemon
        stop_daemon("mvadapter")

        # texture_i2tex uses relative imports → run as module from MV-Adapter root.
        # Torch C++ extensions need `ninja` on PATH (venv bin).
        mv_bin = str(MVADAPTER_ROOT / ".venv" / "bin")
        env = {
            "PATH": f"{mv_bin}:{os.environ.get('PATH', '')}",
            "VIRTUAL_ENV": str(MVADAPTER_ROOT / ".venv"),
        }
        cmd = [
            str(MVADAPTER_PYTHON),
            "-m",
            "scripts.texture_i2tex",
            "--device",
            self.device,
            "--variant",
            "sdxl",
            "--mesh",
            str(mesh),
            "--image",
            str(image),
            "--text",
            self.texture_text or "high quality",
            "--seed",
            str(self.seed),
            "--save_dir",
            str(save_dir),
            "--save_name",
            f"{save_name}_i2tex",
            "--num_inference_steps",
            str(self.texture_steps),
            "--guidance_scale",
            str(self.texture_guidance),
            "--uv_size",
            str(self.texture_uv_size),
            "--remove_bg",
            "--preprocess_mesh",  # always on — required for TripoSG non-manifold meshes
            "--rotation_yaw",
            str(self.rotation_yaw),
            "--rotation_pitch",
            str(self.rotation_pitch),
            "--inpaint_mode",
            str(self.inpaint_mode),
        ]
        _run(cmd, cwd=MVADAPTER_ROOT, env=env, timeout=60 * 45)
        shaded = save_dir / f"{save_name}_i2tex_shaded.glb"
        if not shaded.is_file():
            nested = save_dir / f"{save_name}_i2tex_shaded" / f"{save_name}_i2tex_shaded.glb"
            if nested.is_file():
                shutil.copy2(nested, shaded)
        if not shaded.is_file():
            raise FileNotFoundError(f"MV-Adapter textured mesh missing: {shaded}")
        # Also publish canonical name used by Hunyuan path / newer callers
        canonical = save_dir / f"{save_name}_textured.glb"
        if shaded.resolve() != canonical.resolve():
            shutil.copy2(shaded, canonical)
        return shaded

    def _unirig(self, mesh_tex: Path, out: Path, name: str, rigged: Path) -> None:
        # Check if warm UniRig daemon is online
        if unirig_warm_rig(mesh_tex, rigged, seed=self.seed, faces=self.faces):
            return

        unirig_out = out / "unirig"
        unirig_out.mkdir(exist_ok=True)
        # Short local name: UniRig get_files joins npz_dir with the full path stem;
        # absolute inputs ignore npz_dir and write beside the mesh — keep that folder tidy.
        local_mesh = unirig_out / "mesh.glb"
        if mesh_tex.resolve() != local_mesh.resolve():
            shutil.copy2(mesh_tex, local_mesh)
        skeleton = unirig_out / f"{name}_skeleton.fbx"
        skin = unirig_out / f"{name}_skin.fbx"
        env = _unirig_env()

        _run(
            [
                "bash",
                "launch/inference/generate_skeleton.sh",
                "--input",
                str(local_mesh),
                "--output",
                str(skeleton),
                "--seed",
                str(self.seed),
                "--faces_target_count",
                str(self.faces),
                "--force_override",
                "true",
            ],
            cwd=UNIRIG_ROOT,
            env=env,
            timeout=60 * 30,
        )
        if not skeleton.is_file():
            raise RuntimeError(f"UniRig skeleton missing: {skeleton}")
        _run(
            [
                "bash",
                "launch/inference/generate_skin.sh",
                "--input",
                str(skeleton),
                "--output",
                str(skin),
                "--seed",
                str(self.seed),
                "--force_override",
                "true",
            ],
            cwd=UNIRIG_ROOT,
            env=env,
            timeout=60 * 30,
        )
        if not skin.is_file():
            raise RuntimeError(f"UniRig skin missing: {skin}")
        # merge may warn on Draco but still writes GLB
        merge = subprocess.run(
            [
                "bash",
                "launch/inference/merge.sh",
                "--source",
                str(skin),
                "--target",
                str(local_mesh),
                "--output",
                str(rigged),
            ],
            cwd=str(UNIRIG_ROOT),
            env={**os.environ, **env, "PYTHONUNBUFFERED": "1"},
            timeout=60 * 15,
        )
        if not rigged.is_file():
            raise RuntimeError(
                f"UniRig merge failed (exit {merge.returncode}); missing {rigged}"
            )


def run_game_ready(
    image_path: str | Path,
    output_dir: str | Path,
    *,
    name: str = "asset",
    seed: int = OPTS.seed,
    asset_type: str = OPTS.asset_type,
    faces: int = OPTS.shape_faces,
    triposg_steps: int = OPTS.shape_steps,
    texture_backend: str = OPTS.texture_backend,
    texture_text: str = OPTS.texture_text,
    texture_steps: int = OPTS.texture_steps,
    texture_guidance: float = OPTS.texture_guidance,
    texture_uv_size: int = OPTS.texture_uv_size,
    texture_render_size: int = 1024,
    texture_offload: bool = True,
    texture_subfolder: str = "hunyuan3d-paint-v2-0-turbo",
    texture_preprocess_mesh: bool = OPTS.texture_preprocess_mesh,
    device: str = OPTS.device,
    rotation_yaw: float = 0.0,
    rotation_pitch: float = 0.0,
    inpaint_mode: str = "uv",
) -> PipelineResult:
    pipe = GameReadyPipeline(
        asset_type=asset_type,
        faces=faces,
        triposg_steps=triposg_steps,
        texture_backend=texture_backend,
        texture_text=texture_text,
        texture_steps=texture_steps,
        texture_guidance=texture_guidance,
        texture_uv_size=texture_uv_size,
        texture_render_size=texture_render_size,
        texture_offload=texture_offload,
        texture_subfolder=texture_subfolder,
        texture_preprocess_mesh=texture_preprocess_mesh,
        seed=seed,
        device=device,
        rotation_yaw=rotation_yaw,
        rotation_pitch=rotation_pitch,
        inpaint_mode=inpaint_mode,
    )
    return pipe.run(Path(image_path), Path(output_dir), name=name)


def run_rig_only(
    mesh_path: str | Path,
    output_dir: str | Path,
    *,
    name: str = "asset",
    seed: int = OPTS.seed,
    faces: int = OPTS.shape_faces,
    device: str = OPTS.device,
) -> PipelineResult:
    pipe = GameReadyPipeline(faces=faces, seed=seed, device=device)
    return pipe.run_rig(Path(mesh_path), Path(output_dir), name=name)


def main() -> None:
    p = argparse.ArgumentParser(
        description="TripoSG (shape) -> MV-Adapter (texture) -> UniRig (rig)"
    )
    p.add_argument("--image_path")
    p.add_argument("--mesh_path", help="Existing mesh for --rig-only")
    p.add_argument("--output_dir", default="./output")
    p.add_argument("--output_name", default="asset")
    p.add_argument("--seed", type=int, default=OPTS.seed)
    p.add_argument("--asset_type", default=OPTS.asset_type, choices=["character", "prop"])
    p.add_argument("--rig-only", action="store_true", help="Skip shape & texture; UniRig only")
    p.add_argument(
        "--faces",
        type=int,
        default=None,
        help="Shape-stage face budget (default 35000 = bench_image)",
    )
    p.add_argument("--triposg_steps", type=int, default=OPTS.shape_steps)
    p.add_argument(
        "--texture_backend",
        default=OPTS.texture_backend,
        choices=["mvadapter", "hunyuan"],
        help="mvadapter = Img2Texture bake (bench default); hunyuan = experimental",
    )
    p.add_argument("--texture_text", default=OPTS.texture_text)
    p.add_argument("--texture_steps", type=int, default=OPTS.texture_steps)
    p.add_argument("--texture_guidance", type=float, default=OPTS.texture_guidance)
    p.add_argument("--texture_uv_size", type=int, default=OPTS.texture_uv_size)
    p.add_argument("--texture_render_size", type=int, default=1024)
    p.add_argument(
        "--texture_offload",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument("--texture_subfolder", default="hunyuan3d-paint-v2-0-turbo")
    p.add_argument(
        "--texture_preprocess_mesh",
        action=argparse.BooleanOptionalAction,
        default=OPTS.texture_preprocess_mesh,
    )
    p.add_argument("--device", default=OPTS.device)
    p.add_argument("--rotation_yaw", type=float, default=0.0, help="Yaw rotation offset in degrees for projection")
    p.add_argument("--rotation_pitch", type=float, default=0.0, help="Pitch rotation offset in degrees for projection")
    p.add_argument("--inpaint_mode", type=str, default="uv", choices=["uv", "view"], help="Inpaint blending mode")
    args = p.parse_args()

    if args.faces is None:
        faces = OPTS.prop_shape_faces if args.asset_type == "prop" else OPTS.shape_faces
    else:
        faces = args.faces

    out = Path(args.output_dir) / args.output_name
    if args.rig_only or args.mesh_path:
        if not args.mesh_path:
            raise SystemExit("--mesh_path is required for rig-only")
        result = run_rig_only(
            args.mesh_path,
            out,
            name=args.output_name,
            seed=args.seed,
            faces=faces,
            device=args.device,
        )
    else:
        if not args.image_path:
            raise SystemExit("--image_path is required (or use --rig-only --mesh_path)")
        result = run_game_ready(
            args.image_path,
            out,
            name=args.output_name,
            seed=args.seed,
            asset_type=args.asset_type,
            faces=faces,
            triposg_steps=args.triposg_steps,
            texture_backend=args.texture_backend,
            texture_text=args.texture_text,
            texture_steps=args.texture_steps,
            texture_guidance=args.texture_guidance,
            texture_uv_size=args.texture_uv_size,
            texture_render_size=args.texture_render_size,
            texture_offload=args.texture_offload,
            texture_subfolder=args.texture_subfolder,
            texture_preprocess_mesh=args.texture_preprocess_mesh,
            device=args.device,
            rotation_yaw=args.rotation_yaw,
            rotation_pitch=args.rotation_pitch,
            inpaint_mode=args.inpaint_mode,
        )
    print(asdict(result), flush=True)


if __name__ == "__main__":
    main()
