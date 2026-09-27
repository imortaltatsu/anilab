from __future__ import annotations

import os
from pathlib import Path

from huggingface_hub import hf_hub_download

# anilab/saas/engines/UniRig/src/inference/download.py → repo root is parents[5]
_REPO_WEIGHTS = Path(__file__).resolve().parents[5] / "weights" / "unirig"


def download(ckpt_name: str) -> str:
    MAP = {
        "experiments/skeleton/articulation-xl_quantization_256/model.ckpt": "skeleton/articulation-xl_quantization_256/model.ckpt",
        "experiments/skin/articulation-xl/model.ckpt": "skin/articulation-xl/model.ckpt",
        "experiments/skin/skeleton/model.ckpt": "skin/skeleton/model.ckpt",
    }

    try:
        if ckpt_name not in MAP:
            print(f"not found: {ckpt_name}")
            return ckpt_name
        rel = MAP[ckpt_name]
        env_root = os.environ.get("ANILAB_WEIGHTS")
        candidates = []
        if env_root:
            candidates.append(Path(env_root) / "unirig" / rel)
        candidates.append(_REPO_WEIGHTS / rel)
        for local in candidates:
            if local.is_file():
                return str(local)
        return hf_hub_download(
            repo_id="VAST-AI/UniRig",
            filename=rel,
        )
    except Exception as e:
        print(f"Failed to download {ckpt_name}: {e}")
        return ckpt_name
