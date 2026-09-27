"""Locate SaaS engines (TripoSG, texture, UniRig) and weights/."""
from __future__ import annotations

from pathlib import Path

SAAS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SAAS_ROOT.parent
ENGINES = SAAS_ROOT / "engines"
WEIGHTS = REPO_ROOT / "weights"

TRIPOSG_ROOT = ENGINES / "TripoSG"
MVADAPTER_ROOT = ENGINES / "MV-Adapter"
HUNYUAN3D_ROOT = ENGINES / "Hunyuan3D-2"
HUNYUAN3D21_ROOT = ENGINES / "Hunyuan3D-2.1"
UNIRIG_ROOT = ENGINES / "UniRig"

TRIPOSG_PYTHON = TRIPOSG_ROOT / ".venv" / "bin" / "python"
MVADAPTER_PYTHON = MVADAPTER_ROOT / ".venv" / "bin" / "python"
HUNYUAN3D_PYTHON = HUNYUAN3D_ROOT / ".venv" / "bin" / "python"
HUNYUAN3D21_PYTHON = HUNYUAN3D21_ROOT / ".venv" / "bin" / "python"
UNIRIG_PYTHON = UNIRIG_ROOT / ".venv" / "bin" / "python"

# Local paint/delight snapshot (HF: tencent/Hunyuan3D-2)
HUNYUAN3D_WEIGHTS = WEIGHTS / "hunyuan3d-2"
# Hunyuan3D-2.1 Paint-only (HF: tencent/Hunyuan3D-2.1 / hunyuan3d-paintpbr-v2-1)
HUNYUAN3D21_WEIGHTS = WEIGHTS / "hunyuan3d-2.1"


def validate_engines(*, texture_backend: str = "hy3d21") -> None:
    missing = []
    required = [
        ("TripoSG", TRIPOSG_ROOT),
        ("UniRig", UNIRIG_ROOT),
        ("TripoSG python", TRIPOSG_PYTHON),
        ("UniRig python", UNIRIG_PYTHON),
    ]
    backend = (texture_backend or "hy3d21").strip().lower()
    if backend in ("hy3d21", "hunyuan21", "paint21", "hy3dpaint"):
        required.extend(
            [
                ("Hunyuan3D-2.1", HUNYUAN3D21_ROOT),
                ("Hunyuan3D-2.1 python", HUNYUAN3D21_PYTHON),
            ]
        )
    elif backend in ("hunyuan", "hunyuan3d", "paint"):
        required.extend(
            [
                ("Hunyuan3D-2", HUNYUAN3D_ROOT),
                ("Hunyuan3D-2 python", HUNYUAN3D_PYTHON),
            ]
        )
    else:
        required.extend(
            [
                ("MV-Adapter", MVADAPTER_ROOT),
                ("MV-Adapter python", MVADAPTER_PYTHON),
            ]
        )
    for label, path in required:
        if not path.exists():
            missing.append(f"{label}: {path}")
    if missing:
        raise FileNotFoundError(
            "Missing SaaS engines (install under saas/engines):\n  " + "\n  ".join(missing)
        )
