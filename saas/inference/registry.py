"""Shared weight / engine registry — one place for all pipelines to resolve models."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .paths import (
    MVADAPTER_PYTHON,
    MVADAPTER_ROOT,
    TRIPOSG_PYTHON,
    TRIPOSG_ROOT,
    UNIRIG_PYTHON,
    UNIRIG_ROOT,
    WEIGHTS,
    validate_engines,
)


@dataclass(frozen=True)
class ModelPaths:
    """On-disk artifacts shared across shape / texture / rig pipelines."""

    weights_root: Path
    shape_dir: Path
    shape_rmbg_dir: Path
    texture_adapter: Path
    rig_skeleton_ckpt: Path
    rig_skin_ckpt: Path

    # Engine roots + pythons (separate venvs today; still one registry)
    shape_root: Path
    shape_python: Path
    texture_root: Path
    texture_python: Path
    rig_root: Path
    rig_python: Path


def get_models() -> ModelPaths:
    return ModelPaths(
        weights_root=WEIGHTS,
        shape_dir=WEIGHTS / "triposg" / "TripoSG",
        shape_rmbg_dir=WEIGHTS / "triposg" / "RMBG-1.4",
        texture_adapter=WEIGHTS
        / "mvadapter"
        / "mv-adapter"
        / "mvadapter_ig2mv_sdxl.safetensors",
        rig_skeleton_ckpt=WEIGHTS
        / "unirig"
        / "skeleton"
        / "articulation-xl_quantization_256"
        / "model.ckpt",
        rig_skin_ckpt=WEIGHTS / "unirig" / "skin" / "articulation-xl" / "model.ckpt",
        shape_root=TRIPOSG_ROOT,
        shape_python=TRIPOSG_PYTHON,
        texture_root=MVADAPTER_ROOT,
        texture_python=MVADAPTER_PYTHON,
        rig_root=UNIRIG_ROOT,
        rig_python=UNIRIG_PYTHON,
    )


def validate_models(require_weights: bool = True) -> list[str]:
    """Return list of missing path labels (empty = OK)."""
    missing: list[str] = []
    try:
        validate_engines()
    except FileNotFoundError as exc:
        missing.append(str(exc))
        return missing

    m = get_models()
    if not require_weights:
        return missing

    checks = [
        ("shape weights", m.shape_dir / "model_index.json"),
        ("shape rmbg", m.shape_rmbg_dir / "model.safetensors"),
        ("texture adapter", m.texture_adapter),
        ("rig skeleton ckpt", m.rig_skeleton_ckpt),
        ("rig skin ckpt", m.rig_skin_ckpt),
    ]
    for label, path in checks:
        if not path.is_file():
            missing.append(f"{label}: {path}")
    return missing
