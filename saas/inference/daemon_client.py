"""Client interface to talk to persistent warm engine daemons."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

log = logging.getLogger("yeetgen.daemon_client")

TRIPOSG_PORT = 8101
MVADAPTER_PORT = 8102
UNIRIG_PORT = 8103


def is_daemon_ready(port: int, timeout: float = 2.5) -> bool:
    """Check if a warm engine daemon is responding on localhost:port."""
    url = f"http://127.0.0.1:{port}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "yeetgen/pipeline"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ready"
    except Exception:
        return False
    return False


def _post_json(port: int, endpoint: str, payload: dict[str, Any], timeout: float = 600.0) -> dict[str, Any]:
    url = f"http://127.0.0.1:{port}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "yeetgen/pipeline"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def triposg_warm_generate(
    image_path: Path | str,
    mesh_out: Path | str,
    seed: int = 42,
    faces: int = 35_000,
    steps: int = 50,
) -> bool:
    """Attempt warm in-memory generation via TripoSG daemon."""
    if not is_daemon_ready(TRIPOSG_PORT):
        return False
    try:
        print(f"[pipeline] Dispatching to warm TripoSG daemon on port {TRIPOSG_PORT}...", flush=True)
        res = _post_json(
            TRIPOSG_PORT,
            "/generate",
            {
                "image_input": str(image_path),
                "output_path": str(mesh_out),
                "seed": seed,
                "faces": faces,
                "steps": steps,
            },
            timeout=180.0,
        )
        if res.get("status") == "ok" and Path(mesh_out).is_file():
            print(f"[pipeline] Warm TripoSG finished in {res.get('elapsed_s')}s!", flush=True)
            return True
    except urllib.error.HTTPError as http_err:
        try:
            err_body = http_err.read().decode("utf-8")
            detail = json.loads(err_body).get("detail", err_body)
        except Exception:
            detail = str(http_err)
        raise RuntimeError(f"TripoSG daemon error: {detail}") from http_err
    except Exception as exc:
        log.warning("Warm TripoSG dispatch failed, falling back to CLI: %s", exc)
    return False


def mvadapter_warm_texture(
    mesh: Path | str,
    image: Path | str,
    save_dir: Path | str,
    save_name: str,
    text: str = "high quality",
    seed: int = 42,
    steps: int = 50,
    guidance: float = 4.0,
    uv_size: int = 2048,
    preprocess_mesh: bool = True,
    remove_bg: bool = True,
    rotation_yaw: float = 0.0,
    rotation_pitch: float = 0.0,
    inpaint_mode: str = "uv",
) -> Path | None:
    """Attempt warm in-memory texture baking via MV-Adapter daemon."""
    if not is_daemon_ready(MVADAPTER_PORT):
        return None
    try:
        print(f"[pipeline] Dispatching to warm MV-Adapter daemon on port {MVADAPTER_PORT}...", flush=True)
        res = _post_json(
            MVADAPTER_PORT,
            "/texture",
            {
                "mesh": str(mesh),
                "image": str(image),
                "save_dir": str(save_dir),
                "save_name": save_name,
                "text": text,
                "seed": seed,
                "num_inference_steps": steps,
                "guidance_scale": guidance,
                "uv_size": uv_size,
                "preprocess_mesh": preprocess_mesh,
                "remove_bg": remove_bg,
                "rotation_yaw": rotation_yaw,
                "rotation_pitch": rotation_pitch,
                "inpaint_mode": inpaint_mode,
            },
            timeout=600.0,
        )
        if res.get("status") == "ok":
            out_mesh = Path(res["mesh_out"])
            if out_mesh.is_file():
                print(f"[pipeline] Warm MV-Adapter finished in {res.get('elapsed_s')}s!", flush=True)
                return out_mesh
    except urllib.error.HTTPError as http_err:
        try:
            err_body = http_err.read().decode("utf-8")
            detail = json.loads(err_body).get("detail", err_body)
        except Exception:
            detail = str(http_err)
        raise RuntimeError(f"MV-Adapter daemon error: {detail}") from http_err
    except Exception as exc:
        log.warning("Warm MV-Adapter dispatch failed (connection error), falling back to CLI: %s", exc)
    return None


def unirig_warm_rig(
    input_mesh: Path | str,
    output_mesh: Path | str,
    seed: int = 42,
    faces: int = 35_000,
) -> bool:
    """Attempt warm in-memory auto-rigging via UniRig daemon."""
    if not is_daemon_ready(UNIRIG_PORT):
        return False
    try:
        print(f"[pipeline] Dispatching to warm UniRig daemon on port {UNIRIG_PORT}...", flush=True)
        res = _post_json(
            UNIRIG_PORT,
            "/rig",
            {
                "input_mesh": str(input_mesh),
                "output_mesh": str(output_mesh),
                "seed": seed,
                "faces": faces,
            },
            timeout=600.0,
        )
        if res.get("status") == "ok" and Path(output_mesh).is_file():
            print(f"[pipeline] Warm UniRig finished in {res.get('elapsed_s')}s!", flush=True)
            return True
    except urllib.error.HTTPError as http_err:
        try:
            err_body = http_err.read().decode("utf-8")
            detail = json.loads(err_body).get("detail", err_body)
        except Exception:
            detail = str(http_err)
        raise RuntimeError(f"UniRig daemon error: {detail}") from http_err
    except Exception as exc:
        log.warning("Warm UniRig dispatch failed, falling back to CLI: %s", exc)
    return False
