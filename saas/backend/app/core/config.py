from __future__ import annotations

import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[3]  # saas/
REPO = ROOT.parent  # anilab/
ENGINES = ROOT / "engines"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "yeetgen"
    api_prefix: str = "/api"
    secret_key: str = "dev-change-me-anilab-secret-key"
    access_token_expire_minutes: int = 60 * 24 * 7
    algorithm: str = "HS256"

    # Static admin password (JWT role=admin). Override via ADMIN_PASSWORD.
    admin_password: str = "yeet90"
    # Seeded into allowlist on first boot if the table is empty.
    bootstrap_password: str = "anilab"

    database_url: str = f"sqlite:///{ROOT / 'backend' / 'anilab.db'}"
    upload_dir: Path = ROOT / "storage" / "uploads"
    output_dir: Path = ROOT / "storage" / "outputs"
    jobs_dir: Path = ROOT / "storage" / "jobs"

    saas_root: Path = ROOT
    repo_root: Path = REPO
    pipeline_python: Path = Path(sys.executable)

    triposg_root: Path = ENGINES / "TripoSG"
    mvadapter_root: Path = ENGINES / "MV-Adapter"
    hunyuan3d_root: Path = ENGINES / "Hunyuan3D-2"
    unirig_root: Path = ENGINES / "UniRig"

    # Match saas/storage/outputs/bench_image (iron_boy) 1:1
    faces: int = 35_000
    asset_type: str = "character"  # character | prop (prop skips UniRig only)
    triposg_steps: int = 50
    device: str = "cuda"
    texture_backend: str = "hy3d21"
    texture_text: str = "high quality"
    texture_uv_size: int = 2048
    texture_steps: int = 50
    texture_guidance: float = 4.0
    texture_preprocess_mesh: bool = True
    # One worker thread per GPU id (dual RTX 4000 Ada → 2 concurrent jobs)
    gpu_ids: list[int] = [0, 1]
    max_concurrent_jobs: int = 2
    # Warm only when the queue is idle. Off by default so user jobs aren't delayed.
    warmup_on_startup: bool = False
    warmup_triposg_steps: int = 8
    warmup_faces: int = 8_000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://proxpc:5173",
        "http://proxpc.local:5173",
    ]

    t2i_backend: str = "local"  # local FLUX.2-klein | auto | cloud
    # Full BF16 Diffusers pipeline (FP8 single-file is broken in current diffusers).
    local_t2i_model: str = "black-forest-labs/FLUX.2-klein-4B"
    local_t2i_path: Path | None = ROOT / "weights" / "flux2-klein-4B"
    # Leave empty — BFL FP8 safetensors crash from_single_file (0-dim weight_scale).
    local_t2i_fp8: str = ""
    local_t2i_fp8_path: Path | None = None
    t2i_local_steps: int = 4
    t2i_guidance_scale: float = 1.0
    # Offload T2I modules when free VRAM is tight so other stages can stay warm.
    t2i_offload: bool = True
    xai_api_key: str | None = None
    pollinations_api_key: str | None = None
    # Text→image (stage 1) — portrait for full-body T-pose refs
    t2i_model: str = "sana"
    t2i_width: int = 768
    t2i_height: int = 1024
    t2i_url_template: str = (
        "https://image.pollinations.ai/prompt/{prompt}"
        "?width={width}&height={height}&seed={seed}&model={model}&enhance=false"
    )


settings = Settings()
for d in (settings.upload_dir, settings.output_dir, settings.jobs_dir):
    d.mkdir(parents=True, exist_ok=True)
