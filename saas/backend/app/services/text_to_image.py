"""Text → T-pose reference image (stage 1), then Image → 3D (stage 2).

Primary: local FLUX.2-klein (BF16; optional dequantized FP8 transformer).
Fallback: Pollinations cloud when t2i_backend=auto (never SDXL-Turbo).
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import settings

log = logging.getLogger("anilab.t2i")

_HEADERS = {
    "User-Agent": "yeetgen/1.0 (text-to-image)",
    "Accept": "image/*,*/*",
}

_NEGATIVE = (
    "multiple figures, collage, character sheet, turnaround, grid, "
    "dynamic pose, beauty pose, arms down, arms bent, A-pose, cropped, "
    "missing limbs, extra limbs, text, watermark, blurry, melted"
)


def build_tpose_prompt(prompt: str) -> str:
    """Expand a short character description into a locked single-figure T-pose prompt.

    Subject comes first so CLIP's 77-token limit does not drop the character.
    """
    subject = " ".join(prompt.strip().split())
    if not subject:
        raise ValueError("empty prompt")
    for junk in (
        "standing pose",
        "standing",
        "full body",
        "t-pose",
        "t pose",
        "a-pose",
        "a pose",
        "facing camera",
        "character sheet",
        "turnaround",
        "reference sheet",
    ):
        low = subject.lower()
        if junk in low:
            idx = low.find(junk)
            subject = (subject[:idx] + subject[idx + len(junk) :]).strip(" ,")
            subject = " ".join(subject.split())
    if not subject:
        subject = "character"
    # Keep under ~70 tokens: subject first, then hard pose lock.
    return (
        f"{subject}, "
        "single figure only, strict T-pose, arms horizontal forming a T, "
        "palms forward, legs straight, front view, full body head to toe, "
        "centered, plain light grey studio background, sharp detailed"
    )


def enhance_prompt_for_3d(prompt: str) -> str:
    return build_tpose_prompt(prompt)


def _is_image_bytes(data: bytes, content_type: str) -> bool:
    if data.startswith(b"\x89PNG") or data[:2] == b"\xff\xd8" or data.startswith(b"RIFF"):
        return True
    return "image" in (content_type or "").lower()


def _local_python() -> Path:
    """Prefer TripoSG CUDA venv (has diffusers); fall back to MV-Adapter."""
    candidates = [
        Path(os.environ.get("YEETGEN_T2I_PYTHON", "")),
        settings.triposg_root / ".venv" / "bin" / "python",
        settings.mvadapter_root / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for p in candidates:
        if p and p.is_file():
            return p
    return Path(sys.executable)


def _transformer_ready(model_path: Path) -> bool:
    tdir = model_path / "transformer"
    if not tdir.is_dir():
        return False
    return any(tdir.glob("*.safetensors")) or any(tdir.glob("*.bin"))


def _generate_local_flux(prompt: str, dest: Path, seed: int) -> Path:
    """Run FLUX.2-klein in an engine CUDA venv (no SDXL-Turbo)."""
    py = _local_python()
    script = settings.repo_root / "saas" / "scripts" / "local_tpose_t2i.py"
    if not script.is_file():
        raise FileNotFoundError(script)

    model = settings.local_t2i_model
    local_path = settings.local_t2i_path
    if local_path and Path(local_path).joinpath("model_index.json").is_file():
        model = str(Path(local_path).resolve())

    # FP8 only when BF16 transformer shards are missing (dequant path in script).
    fp8 = (settings.local_t2i_fp8 or "").strip()
    fp8_path = settings.local_t2i_fp8_path
    if fp8_path:
        p = Path(fp8_path)
        if p.is_file() or (p.is_dir() and any(p.glob("*fp8*.safetensors"))):
            fp8 = str(p.resolve())

    model_path = Path(model)
    if model_path.is_dir() and not _transformer_ready(model_path):
        # Prefer dequantized local FP8 over a half-downloaded BF16 tree.
        default_fp8 = settings.saas_root / "weights" / "flux2-klein-4b-fp8"
        if not fp8 and default_fp8.is_dir() and any(default_fp8.glob("*fp8*.safetensors")):
            fp8 = str(default_fp8.resolve())
            log.warning("BF16 transformer missing — using dequantized FP8 from %s", fp8)

    cmd = [
        str(py),
        str(script),
        "--prompt",
        prompt,
        "--out",
        str(dest),
        "--seed",
        str(seed),
        "--width",
        str(settings.t2i_width),
        "--height",
        str(settings.t2i_height),
        "--steps",
        str(settings.t2i_local_steps),
        "--model",
        model,
        "--base_model",
        model,
        "--fp8_transformer",
        fp8,
        "--guidance_scale",
        str(settings.t2i_guidance_scale),
        "--device",
        "cuda",
    ]
    if settings.t2i_offload or "9b" in model.lower():
        cmd.append("--offload")
    log.info("Local Flux T2I: %s", " ".join(cmd[:8]))
    env = os.environ.copy()
    env["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(settings.repo_root),
        env=env,
        timeout=60 * 15,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size < 8_000:
        tail = (proc.stderr or proc.stdout or "")[-1500:]
        raise RuntimeError(f"local FLUX.2-klein failed ({proc.returncode}): {tail}")
    log.info("Local Flux T2I saved %s (%s bytes)", dest, dest.stat().st_size)
    return dest


def _pollinations_urls(prompt: str, seed: int) -> list[str]:
    q = quote(prompt, safe="")
    neg = quote(_NEGATIVE, safe="")
    w = settings.t2i_width
    h = settings.t2i_height
    models = [settings.t2i_model, "sana", "flux"]
    urls: list[str] = []
    for model in models:
        urls.append(
            f"https://image.pollinations.ai/prompt/{q}"
            f"?width={w}&height={h}&seed={seed}&model={model}"
            f"&enhance=false&negative_prompt={neg}"
        )
    out: list[str] = []
    for u in urls:
        if u not in out:
            out.append(u)
    return out


def _download(url: str, dest: Path, *, attempts: int = 3) -> None:
    last_err: Exception | None = None
    timeout = httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=30.0)
    for i in range(attempts):
        try:
            log.info("T2I cloud attempt %s/%s GET %s", i + 1, attempts, url[:160])
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                headers=_HEADERS,
                http2=False,
            ) as client:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    data = b"".join(resp.iter_bytes())
                    ctype = resp.headers.get("content-type", "")
            if not _is_image_bytes(data, ctype):
                raise RuntimeError(f"T2I did not return an image (content-type={ctype})")
            if len(data) < 8_000:
                raise RuntimeError(f"T2I image too small ({len(data)} bytes)")
            dest.write_bytes(data)
            return
        except (httpx.HTTPError, OSError, RuntimeError) as exc:
            last_err = exc
            log.warning("T2I cloud failed (%s): %s", type(exc).__name__, exc)
            time.sleep(min(2**i, 8))
    assert last_err is not None
    raise last_err


def generate_image(prompt: str, dest: Path, seed: int = 42) -> Path:
    """Stage 1: text → T-pose reference PNG for the image→3D pipeline."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    enhanced = build_tpose_prompt(prompt)
    meta = dest.with_suffix(".prompt.txt")
    meta.write_text(
        f"user: {prompt.strip()}\nenhanced: {enhanced}\nnegative: {_NEGATIVE}\n"
        f"backend: {settings.t2i_backend}\nmodel: {settings.local_t2i_model}\nseed: {seed}\n",
        encoding="utf-8",
    )
    log.info("T2I enhanced: %s", enhanced[:280])

    backend = (settings.t2i_backend or "local").lower()
    errors: list[str] = []

    if backend in ("auto", "local", "flux", "flux2", "klein"):
        try:
            return _generate_local_flux(prompt, dest, seed)
        except Exception as exc:
            errors.append(f"local: {type(exc).__name__}: {exc}")
            log.warning("Local Flux T2I failed: %s", exc)
            if backend != "auto":
                raise

    if backend in ("auto", "cloud", "pollinations"):
        for url in _pollinations_urls(enhanced, seed):
            try:
                _download(url, dest)
                log.info("Cloud T2I saved %s (%s bytes)", dest, dest.stat().st_size)
                return dest
            except Exception as exc:
                errors.append(f"cloud: {type(exc).__name__}: {exc}")
                continue

    raise RuntimeError(
        "T-pose image generation failed. Details: " + " | ".join(errors[-4:])
    )
