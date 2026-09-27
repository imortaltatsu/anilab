"""Startup / on-demand pipeline warmup status."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

_lock = threading.Lock()
_STATUS_PATH = settings.jobs_dir / "warmup_status.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def status_path() -> Path:
    return _STATUS_PATH


def read_status() -> dict:
    with _lock:
        if not _STATUS_PATH.is_file():
            return {"state": "idle", "gpus": {}}
        try:
            return json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"state": "unknown", "gpus": {}}


def write_status(payload: dict) -> None:
    with _lock:
        _STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATUS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(_STATUS_PATH)


def mark_gpu(gpu_id: int, *, state: str, **extra) -> dict:
    data = read_status()
    gpus = dict(data.get("gpus") or {})
    entry = {"state": state, "updated_at": _now(), **extra}
    gpus[str(gpu_id)] = entry
    states = [g.get("state") for g in gpus.values()]
    if any(s == "running" for s in states):
        overall = "warming"
    elif states and all(s == "ready" for s in states):
        overall = "ready"
    elif any(s == "failed" for s in states):
        overall = "degraded"
    else:
        overall = data.get("state") or "idle"
    payload = {
        "state": overall,
        "updated_at": _now(),
        "gpus": gpus,
        "warmup_on_startup": settings.warmup_on_startup,
    }
    write_status(payload)
    return payload


def warmup_image() -> Path:
    """Prefer TripoSG demo asset, else MV-Adapter demo."""
    candidates = [
        settings.triposg_root / "assets" / "example_data" / "hjswed.png",
        settings.mvadapter_root
        / "assets"
        / "demo"
        / "i2mv"
        / "A_decorative_figurine_of_a_young_anime-style_girl.png",
        settings.saas_root / "frontend" / "src" / "assets" / "hero.png",
    ]
    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError("No warmup image found under engines/assets")
