#!/usr/bin/env python3
"""Dry-test / smoke-test yeetgen inference (TripoSG → MV-Adapter → UniRig).

Default is a non-GPU dry run: validates engines, weights, imports, and prints the
optimized command lines that would execute.

  # Validate only (no GPU)
  python -m saas.scripts.dry_test_inference

  # Short GPU smoke with optimized knobs (GPU 0)
  python -m saas.scripts.dry_test_inference --smoke --gpu 0

  # Stages only
  python -m saas.scripts.dry_test_inference --smoke --stages triposg,unirig
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Allow `python -m saas.scripts.dry_test_inference` from repo root
REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from saas.inference.paths import (  # noqa: E402
    MVADAPTER_PYTHON,
    MVADAPTER_ROOT,
    TRIPOSG_PYTHON,
    TRIPOSG_ROOT,
    UNIRIG_PYTHON,
    UNIRIG_ROOT,
    WEIGHTS,
    validate_engines,
)


# Smoke knobs (lower than production for quick GPU checks; production = 35k/50)
OPT = {
    "triposg_steps": 12,
    "triposg_faces": 12000,
    "mv_steps": 12,
    "uv_size": 2048,
    "unirig_faces": 12000,
    "unirig_beams_target": 4,
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    mode: str
    checks: list[CheckResult] = field(default_factory=list)
    commands: list[list[str]] = field(default_factory=list)
    timings: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks) and not self.errors


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str], timeout: int) -> None:
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"exit {proc.returncode}: {' '.join(cmd)}")


def _base_env(gpu: int) -> dict[str, str]:
    e = os.environ.copy()
    e.pop("TQDM_ASCII", None)
    e["PYTHONUNBUFFERED"] = "1"
    e["ANILAB_WEIGHTS"] = str(WEIGHTS)
    e["CUDA_VISIBLE_DEVICES"] = str(gpu)
    e["TQDM_NCOLS"] = "100"
    e["COLUMNS"] = "100"
    e["TERM"] = "xterm-256color"
    e["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    return e


def check_layout() -> list[CheckResult]:
    out: list[CheckResult] = []
    try:
        validate_engines()
        out.append(CheckResult("engines", True, "TripoSG / MV-Adapter / UniRig + venvs"))
    except Exception as exc:
        out.append(CheckResult("engines", False, str(exc)))

    pairs = [
        ("weights/triposg", WEIGHTS / "triposg" / "TripoSG" / "model_index.json"),
        ("weights/rmbg", WEIGHTS / "triposg" / "RMBG-1.4" / "model.safetensors"),
        ("weights/mvadapter", WEIGHTS / "mvadapter" / "mv-adapter" / "mvadapter_ig2mv_sdxl.safetensors"),
        ("weights/unirig_skel", WEIGHTS / "unirig" / "skeleton" / "articulation-xl_quantization_256" / "model.ckpt"),
        ("weights/unirig_skin", WEIGHTS / "unirig" / "skin" / "articulation-xl" / "model.ckpt"),
    ]
    for name, path in pairs:
        out.append(CheckResult(name, path.is_file(), str(path)))

    sample = TRIPOSG_ROOT / "assets" / "example_data" / "hjswed.png"
    out.append(CheckResult("sample_image", sample.is_file(), str(sample)))
    return out


def check_imports(gpu: int) -> list[CheckResult]:
    out: list[CheckResult] = []
    probes = [
        (
            "triposg_torch",
            TRIPOSG_PYTHON,
            "import torch; print(torch.__version__, torch.cuda.is_available())",
        ),
        (
            "mvadapter_torch",
            MVADAPTER_PYTHON,
            "import torch; print(torch.__version__, torch.cuda.is_available())",
        ),
        (
            "unirig_torch",
            UNIRIG_PYTHON,
            "import torch; print(torch.__version__, torch.cuda.is_available())",
        ),
    ]
    env = _base_env(gpu)
    for name, py, code in probes:
        try:
            proc = subprocess.run(
                [str(py), "-c", code],
                cwd=str(REPO),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            ok = proc.returncode == 0 and "True" in (proc.stdout or "")
            detail = (proc.stdout or proc.stderr or "").strip()[:200]
            out.append(CheckResult(name, ok, detail))
        except Exception as exc:
            out.append(CheckResult(name, False, str(exc)))
    return out


def planned_commands(image: Path, out_dir: Path, mesh_for_rig: Path | None) -> list[tuple[str, list[str], Path]]:
    """Return (stage, cmd, cwd) for optimized smoke settings."""
    mesh_raw = out_dir / "mesh_raw.glb"
    shaded = out_dir / "dry_i2tex_shaded.glb"
    cmds: list[tuple[str, list[str], Path]] = []

    tripo_env_path = (
        f"{TRIPOSG_ROOT}{os.pathsep}{TRIPOSG_ROOT / 'scripts'}"
    )
    cmds.append(
        (
            "triposg",
            [
                str(TRIPOSG_PYTHON),
                str(TRIPOSG_ROOT / "scripts" / "inference_triposg.py"),
                "--image-input",
                str(image),
                "--output-path",
                str(mesh_raw),
                "--seed",
                "0",
                "--num-inference-steps",
                str(OPT["triposg_steps"]),
                "--faces",
                str(OPT["triposg_faces"]),
            ],
            TRIPOSG_ROOT,
        )
    )

    mv_bin = str(MVADAPTER_ROOT / ".venv" / "bin")
    cmds.append(
        (
            "mvadapter",
            [
                str(MVADAPTER_PYTHON),
                "-m",
                "scripts.texture_i2tex",
                "--device",
                "cuda",
                "--variant",
                "sdxl",
                "--mesh",
                str(mesh_raw),
                "--image",
                str(image),
                "--text",
                "high quality",
                "--seed",
                "0",
                "--save_dir",
                str(out_dir),
                "--save_name",
                "dry_i2tex",
                "--preprocess_mesh",
                "--remove_bg",
            ],
            MVADAPTER_ROOT,
        )
    )

    rig_mesh = mesh_for_rig or shaded
    local = out_dir / "unirig" / "mesh.glb"
    skeleton = out_dir / "unirig" / "skeleton.fbx"
    skin = out_dir / "unirig" / "skin.fbx"
    final = out_dir / "mesh.glb"
    cmds.append(
        (
            "unirig_skeleton",
            [
                "bash",
                "launch/inference/generate_skeleton.sh",
                "--input",
                str(local),
                "--output",
                str(skeleton),
                "--seed",
                "0",
                "--faces_target_count",
                str(OPT["unirig_faces"]),
                "--force_override",
                "true",
            ],
            UNIRIG_ROOT,
        )
    )
    cmds.append(
        (
            "unirig_skin",
            [
                "bash",
                "launch/inference/generate_skin.sh",
                "--input",
                str(skeleton),
                "--output",
                str(skin),
                "--seed",
                "0",
                "--force_override",
                "true",
            ],
            UNIRIG_ROOT,
        )
    )
    cmds.append(
        (
            "unirig_merge",
            [
                "bash",
                "launch/inference/merge.sh",
                "--source",
                str(skin),
                "--target",
                str(local),
                "--output",
                str(final),
            ],
            UNIRIG_ROOT,
        )
    )
    # silence unused
    _ = (tripo_env_path, mv_bin, rig_mesh)
    return cmds


def run_smoke(
    *,
    stages: set[str],
    gpu: int,
    out_dir: Path,
    image: Path,
    existing_mesh: Path | None,
) -> Report:
    report = Report(mode="smoke")
    report.checks.extend(check_layout())
    report.checks.extend(check_imports(gpu))
    if not all(c.ok for c in report.checks):
        report.errors.append("preflight checks failed")
        return report

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "unirig").mkdir(exist_ok=True)
    env = _base_env(gpu)
    env["PYTHONPATH"] = (
        f"{TRIPOSG_ROOT}{os.pathsep}{TRIPOSG_ROOT / 'scripts'}"
        + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    )

    mesh_raw = out_dir / "mesh_raw.glb"
    shaded = out_dir / "dry_i2tex_shaded.glb"

    if "triposg" in stages:
        t0 = time.perf_counter()
        try:
            cmd = [
                str(TRIPOSG_PYTHON),
                str(TRIPOSG_ROOT / "scripts" / "inference_triposg.py"),
                "--image-input",
                str(image),
                "--output-path",
                str(mesh_raw),
                "--seed",
                "0",
                "--num-inference-steps",
                str(OPT["triposg_steps"]),
                "--faces",
                str(OPT["triposg_faces"]),
            ]
            report.commands.append(cmd)
            _run(cmd, cwd=TRIPOSG_ROOT, env=env, timeout=60 * 20)
            if not mesh_raw.is_file():
                raise RuntimeError(f"missing {mesh_raw}")
            report.timings["triposg_s"] = round(time.perf_counter() - t0, 3)
            report.checks.append(CheckResult("smoke_triposg", True, f"{mesh_raw.stat().st_size} bytes"))
        except Exception as exc:
            report.timings["triposg_s"] = round(time.perf_counter() - t0, 3)
            report.errors.append(f"triposg: {exc}")
            report.checks.append(CheckResult("smoke_triposg", False, str(exc)))
            return report

    if "mvadapter" in stages:
        if not mesh_raw.is_file():
            report.errors.append("mvadapter needs mesh_raw.glb (run triposg or provide --mesh)")
            return report
        t0 = time.perf_counter()
        try:
            mv_env = env.copy()
            mv_bin = str(MVADAPTER_ROOT / ".venv" / "bin")
            mv_env["PATH"] = f"{mv_bin}:{mv_env.get('PATH', '')}"
            mv_env["VIRTUAL_ENV"] = str(MVADAPTER_ROOT / ".venv")
            cmd = [
                str(MVADAPTER_PYTHON),
                "-m",
                "scripts.texture_i2tex",
                "--device",
                "cuda",
                "--variant",
                "sdxl",
                "--mesh",
                str(mesh_raw),
                "--image",
                str(image),
                "--text",
                "high quality",
                "--seed",
                "0",
                "--save_dir",
                str(out_dir),
                "--save_name",
                "dry_i2tex",
                "--preprocess_mesh",
                "--remove_bg",
            ]
            report.commands.append(cmd)
            print(
                f"[note] MV steps still hardcoded=50 in texture_i2tex; "
                f"dry target OPT.mv_steps={OPT['mv_steps']}, uv_size={OPT['uv_size']}",
                flush=True,
            )
            _run(cmd, cwd=MVADAPTER_ROOT, env=mv_env, timeout=60 * 45)
            if not shaded.is_file():
                raise RuntimeError(f"missing {shaded}")
            report.timings["mvadapter_s"] = round(time.perf_counter() - t0, 3)
            report.checks.append(CheckResult("smoke_mvadapter", True, f"{shaded.stat().st_size} bytes"))
        except Exception as exc:
            report.timings["mvadapter_s"] = round(time.perf_counter() - t0, 3)
            report.errors.append(f"mvadapter: {exc}")
            report.checks.append(CheckResult("smoke_mvadapter", False, str(exc)))
            return report

    if "unirig" in stages:
        src = shaded if shaded.is_file() else existing_mesh
        if src is None or not Path(src).is_file():
            report.errors.append("unirig needs textured mesh (mvadapter output or --mesh)")
            return report
        t0 = time.perf_counter()
        try:
            local = out_dir / "unirig" / "mesh.glb"
            shutil.copy2(src, local)
            uenv = env.copy()
            uenv["PATH"] = f"{UNIRIG_ROOT / '.venv' / 'bin'}:{uenv.get('PATH', '')}"
            uenv["VIRTUAL_ENV"] = str(UNIRIG_ROOT / ".venv")
            skeleton = out_dir / "unirig" / "skeleton.fbx"
            skin = out_dir / "unirig" / "skin.fbx"
            final = out_dir / "mesh.glb"
            print(
                f"[note] UniRig AR num_beams still 15 in yaml; "
                f"dry target OPT.unirig_beams_target={OPT['unirig_beams_target']}",
                flush=True,
            )
            for label, cmd in (
                (
                    "unirig_skeleton",
                    [
                        "bash",
                        "launch/inference/generate_skeleton.sh",
                        "--input",
                        str(local),
                        "--output",
                        str(skeleton),
                        "--seed",
                        "0",
                        "--faces_target_count",
                        str(OPT["unirig_faces"]),
                        "--force_override",
                        "true",
                    ],
                ),
                (
                    "unirig_skin",
                    [
                        "bash",
                        "launch/inference/generate_skin.sh",
                        "--input",
                        str(skeleton),
                        "--output",
                        str(skin),
                        "--seed",
                        "0",
                        "--force_override",
                        "true",
                    ],
                ),
                (
                    "unirig_merge",
                    [
                        "bash",
                        "launch/inference/merge.sh",
                        "--source",
                        str(skin),
                        "--target",
                        str(local),
                        "--output",
                        str(final),
                    ],
                ),
            ):
                report.commands.append(cmd)
                _run(cmd, cwd=UNIRIG_ROOT, env=uenv, timeout=60 * 30)
            if not final.is_file():
                raise RuntimeError(f"missing {final}")
            report.timings["unirig_s"] = round(time.perf_counter() - t0, 3)
            report.checks.append(CheckResult("smoke_unirig", True, f"{final.stat().st_size} bytes"))
        except Exception as exc:
            report.timings["unirig_s"] = round(time.perf_counter() - t0, 3)
            report.errors.append(f"unirig: {exc}")
            report.checks.append(CheckResult("smoke_unirig", False, str(exc)))

    report.timings["total_s"] = round(sum(v for k, v in report.timings.items() if k.endswith("_s")), 3)
    return report


def run_dry(gpu: int, image: Path, out_dir: Path) -> Report:
    report = Report(mode="dry")
    report.checks.extend(check_layout())
    report.checks.extend(check_imports(gpu))
    for stage, cmd, cwd in planned_commands(image, out_dir, None):
        report.commands.append(cmd)
        print(f"[dry] {stage} @ {cwd}")
        print("     ", " ".join(cmd))
    print("\n[opt knobs]", json.dumps(OPT, indent=2))
    print(
        "\n[gaps] Still need code wiring for: MV step/uv CLI, UniRig num_beams yaml, "
        "TripoSG fuse_qkv / torch.compile"
    )
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="Dry / smoke test yeetgen inference")
    p.add_argument("--smoke", action="store_true", help="Run short GPU smoke tests")
    p.add_argument("--gpu", type=int, default=0)
    p.add_argument(
        "--stages",
        default="triposg,mvadapter,unirig",
        help="Comma list for --smoke: triposg,mvadapter,unirig",
    )
    p.add_argument(
        "--image",
        default=str(TRIPOSG_ROOT / "assets" / "example_data" / "hjswed.png"),
    )
    p.add_argument(
        "--mesh",
        default="",
        help="Optional existing textured GLB for unirig-only smoke",
    )
    p.add_argument(
        "--out",
        default=str(REPO / "saas" / "storage" / "outputs" / "dry_test"),
    )
    args = p.parse_args()

    image = Path(args.image)
    out_dir = Path(args.out)
    mesh = Path(args.mesh) if args.mesh else None
    stages = {s.strip() for s in args.stages.split(",") if s.strip()}

    if args.smoke:
        # Prefer existing textured mesh for unirig-only / resume
        if mesh is None and "triposg" not in stages and "mvadapter" not in stages:
            candidate = REPO / "saas" / "storage" / "outputs" / "job_5" / "asset" / "mesh.glb"
            if candidate.is_file():
                mesh = candidate
        report = run_smoke(
            stages=stages,
            gpu=args.gpu,
            out_dir=out_dir,
            image=image,
            existing_mesh=mesh,
        )
    else:
        report = run_dry(args.gpu, image, out_dir)

    payload = {
        "ok": report.ok,
        "mode": report.mode,
        "opt": OPT,
        "checks": [asdict(c) for c in report.checks],
        "timings": report.timings,
        "errors": report.errors,
        "commands": report.commands,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / ("smoke_report.json" if args.smoke else "dry_report.json")
    report_path.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2), flush=True)
    print(f"Wrote {report_path}", flush=True)
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
