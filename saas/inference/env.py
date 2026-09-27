"""Shared subprocess / CUDA environment for every engine stage."""
from __future__ import annotations

import os
from pathlib import Path

from .paths import WEIGHTS
from .registry import get_models


def pipeline_env(
    *,
    gpu_id: int | None = None,
    extra: dict[str, str] | None = None,
    include_shape_pythonpath: bool = False,
) -> dict[str, str]:
    """Env shared by shape / texture / rig child processes."""
    e = os.environ.copy()
    e["PYTHONUNBUFFERED"] = "1"
    e["ANILAB_WEIGHTS"] = str(WEIGHTS)
    e.pop("TQDM_ASCII", None)  # breaks hf/tqdm under piped stdout
    e["TQDM_NCOLS"] = e.get("TQDM_NCOLS") or "100"
    e["COLUMNS"] = e.get("COLUMNS") or "100"
    e["TERM"] = e.get("TERM") or "xterm-256color"
    e["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    if gpu_id is not None:
        e["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        e["ANILAB_GPU_ID"] = str(gpu_id)

    models = get_models()
    if include_shape_pythonpath:
        pp = f"{models.shape_root}{os.pathsep}{models.shape_root / 'scripts'}"
        e["PYTHONPATH"] = pp + (os.pathsep + e["PYTHONPATH"] if e.get("PYTHONPATH") else "")

    if extra:
        e.update(extra)
        e.pop("TQDM_ASCII", None)
    return e


def texture_env(base: dict[str, str] | None = None) -> dict[str, str]:
    e = dict(base or pipeline_env())
    models = get_models()
    bin_dir = str(models.texture_root / ".venv" / "bin")
    e["PATH"] = f"{bin_dir}:{e.get('PATH', '')}"
    e["VIRTUAL_ENV"] = str(models.texture_root / ".venv")
    return e


def rig_env(base: dict[str, str] | None = None) -> dict[str, str]:
    e = dict(base or pipeline_env())
    models = get_models()
    bin_dir = str(models.rig_root / ".venv" / "bin")
    e["PATH"] = f"{bin_dir}:{e.get('PATH', '')}"
    e["VIRTUAL_ENV"] = str(models.rig_root / ".venv")
    return e


def ensure_rig_beams(beams: int) -> Path:
    """Write a small overlay task snippet path is not needed — patch runtime yaml copy.

    Returns path to a yeetgen-local skeleton task yaml with reduced beam search.
    """
    from .paths import SAAS_ROOT, UNIRIG_ROOT
    import shutil

    src = UNIRIG_ROOT / "configs" / "system" / "ar_inference_articulationxl.yaml"
    dst_dir = SAAS_ROOT / "inference" / "overlays"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"ar_inference_beams_{beams}.yaml"
    text = src.read_text(encoding="utf-8")
    # Replace num_beams line
    lines = []
    for line in text.splitlines(True):
        if line.strip().startswith("num_beams:"):
            lines.append(f"  num_beams: {int(beams)}\n")
        else:
            lines.append(line)
    dst.write_text("".join(lines), encoding="utf-8")

    # Also need a task yaml that points at this system config — copy task and rewrite
    task_src = UNIRIG_ROOT / "configs" / "task" / "quick_inference_skeleton_articulationxl_ar_256.yaml"
    task_dst = dst_dir / f"quick_skeleton_beams_{beams}.yaml"
    # Task files use relative component names; keep components, override via env is harder.
    # Simpler: patch the live system yaml in-place under overlays and point generate via
    # YEETGEN by copying full task tree reference.
    # For UniRig, system is loaded from task.components.system — rewrite task overlay.
    import yaml  # type: ignore

    try:
        task = yaml.safe_load(task_src.read_text(encoding="utf-8"))
    except Exception:
        # Fallback: copy original task; beams overlay applied by copying system into engine
        shutil.copy2(src, UNIRIG_ROOT / "configs" / "system" / "ar_inference_articulationxl.yaml.bak")
        # Don't overwrite upstream permanently — write beside and return original
        return task_src

    # Point system component at absolute overlay if supported — UniRig joins configs/system/
    # So install overlay as a named system config inside the engine (symlink/copy once).
    engine_sys = UNIRIG_ROOT / "configs" / "system" / f"ar_inference_yeetgen_beams_{beams}.yaml"
    if not engine_sys.is_file() or engine_sys.read_text(encoding="utf-8") != dst.read_text(encoding="utf-8"):
        engine_sys.write_text(dst.read_text(encoding="utf-8"), encoding="utf-8")

    task = dict(task or {})
    comps = dict(task.get("components") or {})
    comps["system"] = f"ar_inference_yeetgen_beams_{beams}"
    task["components"] = comps
    # Write task into engine configs/task so relative loads work
    engine_task = UNIRIG_ROOT / "configs" / "task" / f"yeetgen_skeleton_beams_{beams}.yaml"
    engine_task.write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")
    return engine_task
