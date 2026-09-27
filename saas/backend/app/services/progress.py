"""Parse tqdm-style progress lines and map pipeline stages to overall % / ETA."""
from __future__ import annotations

import json
import re
from pathlib import Path

# Example: 45%|████ | 45/100 [00:54<01:06, 1.21s/it]
_TQDM_RE = re.compile(
    r"(?P<pct>\d+(?:\.\d+)?)%\|"
    r".*?"
    r"(?P<cur>\d+)/(?P<total>\d+)"
    r"\s*\["
    r"(?P<elapsed>[^<]+)"
    r"<"
    r"(?P<remain>[^\],]+)"
)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Overall pipeline weights (sum ≈ 1.0)
STAGE_WEIGHTS = {
    "t2i": 0.05,
    "shape": 0.30,
    "texture": 0.40,
    "rig": 0.25,
}

STAGE_ORDER = {
    "image": ["shape", "texture", "rig"],
    "text": ["t2i", "shape", "texture", "rig"],
    "rig": ["rig"],
}

STAGE_LABEL = {
    "t2i": "Text → image",
    "shape": "Shape (TripoSG)",
    "texture": "Texture (MV-Adapter)",
    "rig": "Rig (UniRig)",
}


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def parse_tqdm(line: str) -> dict | None:
    m = _TQDM_RE.search(line)
    if not m:
        return None
    remain = m.group("remain").strip()
    eta_s = _parse_hms(remain)
    return {
        "pct": float(m.group("pct")),
        "cur": int(m.group("cur")),
        "total": int(m.group("total")),
        "eta_s": eta_s,
        "eta_raw": remain,
        "rate": None,
    }


def _parse_hms(token: str) -> float | None:
    """Parse tqdm remain like 01:06 or 1:02:03 into seconds."""
    token = token.strip()
    if not token or token in ("?", "-"):
        return None
    parts = token.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return None


def detect_stage(line: str, current: str | None) -> str | None:
    low = line.lower()
    if "t2i" in low or "text-to-image" in low or "pollinations" in low:
        return "t2i"
    if "inference_triposg" in low or "triposg" in low or "mesh saved" in low:
        return "shape"
    if (
        "texture_i2tex" in low
        or "mv-adapter" in low
        or "mvadapter" in low
        or "pipeline ready" in low
        or "loading pipeline" in low
    ):
        return "texture"
    if (
        "generate_skeleton" in low
        or "generate_skin" in low
        or "unirig" in low
        or "merge.sh" in low
    ):
        return "rig"
    return current


def overall_progress(
    *,
    mode: str,
    stage: str | None,
    stage_pct: float | None,
    stage_eta_s: float | None,
) -> dict:
    order = STAGE_ORDER.get(mode, STAGE_ORDER["image"])
    # renormalize weights for this mode
    weights = {s: STAGE_WEIGHTS.get(s, 0.25) for s in order}
    total_w = sum(weights.values()) or 1.0
    weights = {k: v / total_w for k, v in weights.items()}

    done = 0.0
    found = False
    for s in order:
        w = weights[s]
        if stage is None:
            break
        if s == stage:
            found = True
            frac = max(0.0, min(1.0, (stage_pct or 0.0) / 100.0))
            done += w * frac
            break
        done += w
    if stage and not found:
        # unknown stage — keep previous-ish midpoint
        done = min(0.95, done + 0.1)

    overall_pct = round(done * 100.0, 1)

    # ETA: remaining weight / current stage rate estimate from stage ETA
    eta_s = None
    if stage and stage_eta_s is not None and stage in weights:
        frac = max(0.0, min(1.0, (stage_pct or 0.0) / 100.0))
        remain_stage_w = weights[stage] * (1.0 - frac)
        # If stage is X% done with eta_stage left, full stage duration ≈ eta/(1-frac)
        if frac < 0.999:
            stage_full = stage_eta_s / max(1e-3, 1.0 - frac)
            # remaining after this stage
            after = sum(weights[s] for s in order[order.index(stage) + 1 :])
            # scale remaining later stages by same stage_full / weight_stage
            rate = stage_full / max(1e-3, weights[stage])  # seconds per unit weight
            eta_s = remain_stage_w * rate + after * rate
        else:
            after = sum(weights[s] for s in order[order.index(stage) + 1 :])
            if after <= 0:
                eta_s = 0.0
            elif stage_eta_s is not None:
                # just finished stage; rough leftover
                eta_s = after / max(1e-3, weights[stage]) * max(stage_eta_s, 1.0)

    return {
        "overall_pct": overall_pct,
        "eta_s": None if eta_s is None else round(float(eta_s), 1),
        "stage": stage,
        "stage_label": STAGE_LABEL.get(stage or "", stage),
        "stage_pct": stage_pct,
        "stages": order,
    }


def write_progress(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_progress(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
