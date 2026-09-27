"""Shared optimized inference knobs — single source for SaaS worker, CLI, dry-tests.

Defaults: TripoSG 35k/50 + Hunyuan3D-Paint + UniRig 35k.
Override any field via env ``YEETGEN_<NAME>`` (e.g. ``YEETGEN_SHAPE_STEPS=28``).
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


@dataclass(frozen=True)
class InferenceOpts:
    """Production defaults — 1:1 with saas/storage/outputs/bench_image."""

    asset_type: str = "character"

    # Shape (TripoSG) — bench: --faces 35000 --num-inference-steps 50
    shape_steps: int = 50
    shape_guidance: float = 7.0
    shape_faces: int = 35_000
    prop_shape_faces: int = 35_000
    shape_fuse_qkv: bool = True

    # Texture — Hunyuan3D-2.1 Paint-only (PBR). Fallbacks: hunyuan (2.0), mvadapter.
    texture_backend: str = "hy3d21"
    texture_steps: int = 50
    texture_guidance: float = 4.0
    texture_variant: str = "sdxl"
    texture_uv_size: int = 2048
    texture_text: str = "high quality"
    texture_preprocess_mesh: bool = True

    # Rig (UniRig) — bench: --faces_target_count 35000
    rig_faces: int = 35_000
    rig_beams: int = 4

    # Warmup / dry smoke
    smoke_shape_steps: int = 12
    smoke_faces: int = 8_000

    # Shared runtime
    device: str = "cuda"
    seed: int = 42

    def to_dict(self) -> dict:
        return asdict(self)


def load_opts() -> InferenceOpts:
    return InferenceOpts(
        asset_type=_env_str("YEETGEN_ASSET_TYPE", "character"),
        shape_steps=_env_int("YEETGEN_SHAPE_STEPS", 50),
        shape_guidance=_env_float("YEETGEN_SHAPE_GUIDANCE", 7.0),
        shape_faces=_env_int("YEETGEN_SHAPE_FACES", 35_000),
        prop_shape_faces=_env_int("YEETGEN_PROP_SHAPE_FACES", 35_000),
        shape_fuse_qkv=os.environ.get("YEETGEN_SHAPE_FUSE_QKV", "1") not in ("0", "false", "False"),
        texture_backend=_env_str("YEETGEN_TEXTURE_BACKEND", "hy3d21"),
        texture_steps=_env_int("YEETGEN_TEXTURE_STEPS", 50),
        texture_guidance=_env_float("YEETGEN_TEXTURE_GUIDANCE", 4.0),
        texture_variant=_env_str("YEETGEN_TEXTURE_VARIANT", "sdxl"),
        texture_uv_size=_env_int("YEETGEN_TEXTURE_UV_SIZE", 2048),
        texture_text=_env_str("YEETGEN_TEXTURE_TEXT", "high quality"),
        texture_preprocess_mesh=os.environ.get("YEETGEN_TEXTURE_PREPROCESS", "1")
        not in ("0", "false", "False"),
        rig_faces=_env_int("YEETGEN_RIG_FACES", 35_000),
        rig_beams=_env_int("YEETGEN_RIG_BEAMS", 4),
        smoke_shape_steps=_env_int("YEETGEN_SMOKE_SHAPE_STEPS", 12),
        smoke_faces=_env_int("YEETGEN_SMOKE_FACES", 8_000),
        device=_env_str("YEETGEN_DEVICE", "cuda"),
        seed=_env_int("YEETGEN_SEED", 42),
    )


# Module-level singleton for importers
OPTS = load_opts()
