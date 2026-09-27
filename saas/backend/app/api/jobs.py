import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_current_principal
from app.core.config import settings
from app.models.db import Job, get_db
from app.models.schemas import (
    JobCreateText,
    JobFromTposePreview,
    JobOut,
    JobRebakeRequest,
    TposePreviewOut,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])

ALLOWED_IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
ALLOWED_MESH = {".glb", ".gltf", ".obj", ".fbx", ".ply"}


def _preview_image_path(job: Job) -> Path | None:
    """Reference image for a job: T2I output, then uploaded / prepared input."""
    out = settings.output_dir / f"job_{job.id}"
    for candidate in (
        out / "t2i_image.png",
        out / "asset" / "t2i_image.png",
        out / "asset" / "processed_image.png",
    ):
        if candidate.is_file():
            return candidate
    if job.input_path:
        p = Path(job.input_path)
        if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE:
            return p
    return None


def _job_out(job: Job) -> JobOut:
    download = f"/api/jobs/{job.id}/download" if job.status == "completed" and job.glb_path else None
    preview = f"/api/jobs/{job.id}/preview" if _preview_image_path(job) else None
    return JobOut(
        id=job.id,
        status=job.status,
        mode=job.mode,
        asset_type=getattr(job, "asset_type", None) or "character",
        prompt=job.prompt,
        glb_path=job.glb_path,
        error=job.error,
        seed=job.seed,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        download_url=download,
        preview_url=preview,
    )


def _owned(job: Job, principal: Principal) -> bool:
    if principal.is_admin:
        return True
    return job.owner == principal.subject


@router.get("", response_model=list[JobOut])
def list_jobs(principal: Principal = Depends(get_current_principal), db: Session = Depends(get_db)):
    q = select(Job).order_by(Job.id.desc())
    if not principal.is_admin:
        q = q.where(Job.owner == principal.subject)
    jobs = db.scalars(q).all()
    return [_job_out(j) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None or not _owned(job, principal):
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(job)


@router.post("/image", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_image_job(
    file: UploadFile = File(...),
    seed: int = Form(42),
    asset_type: str = Form("character"),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    if asset_type not in ("character", "prop"):
        raise HTTPException(status_code=400, detail="asset_type must be character|prop")
    suffix = Path(file.filename or "input.png").suffix.lower()
    if suffix not in ALLOWED_IMAGE:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {suffix}")
    dest = settings.upload_dir / f"{principal.subject.replace(':', '_')}_{uuid.uuid4().hex}{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    job = Job(
        owner=principal.subject,
        status="queued",
        mode="image",
        asset_type=asset_type,
        input_path=str(dest),
        seed=seed,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_out(job)


@router.post("/text/preview", response_model=TposePreviewOut)
def preview_tpose_image(
    body: JobCreateText,
    principal: Principal = Depends(get_current_principal),
):
    """Generate a T-pose studio reference without queueing the 3D pipeline."""
    from app.services.text_to_image import generate_image

    dest = settings.upload_dir / f"tpose_{principal.subject.replace(':', '_')}_{uuid.uuid4().hex}.png"
    try:
        generate_image(body.prompt, dest, seed=body.seed)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"T-pose generation failed: {exc}") from exc
    name = dest.name
    return TposePreviewOut(
        preview_url=f"/api/jobs/preview-upload/{name}",
        filename=name,
        seed=body.seed,
        prompt=body.prompt,
    )


@router.get("/preview-upload/{filename}")
def get_preview_upload(
    filename: str,
    principal: Principal = Depends(get_current_principal),
):
    """Serve a freshly generated T-pose preview from the upload dir."""
    safe = Path(filename).name
    if not safe.startswith("tpose_") or not safe.endswith(".png"):
        raise HTTPException(status_code=404, detail="Not found")
    slug = principal.subject.replace(":", "_")
    if not principal.is_admin and not safe.startswith(f"tpose_{slug}_"):
        raise HTTPException(status_code=404, detail="Not found")
    path = settings.upload_dir / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Preview expired")
    return FileResponse(path, media_type="image/png", filename=safe)


@router.post("/text", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_text_job(
    body: JobCreateText,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    job = Job(
        owner=principal.subject,
        status="queued",
        mode="text",
        asset_type=body.asset_type,
        prompt=body.prompt,
        seed=body.seed,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_out(job)


@router.post("/text/from-preview", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job_from_tpose_preview(
    body: JobFromTposePreview,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Queue Image→3D using an already-generated T-pose preview PNG (after user consent)."""
    safe = Path(body.filename).name
    path = settings.upload_dir / safe
    slug = principal.subject.replace(":", "_")
    owned = safe.startswith(f"tpose_{slug}_") or (
        principal.is_admin and safe.startswith("tpose_") and safe.endswith(".png")
    )
    if not path.is_file() or not owned:
        raise HTTPException(status_code=404, detail="Preview image not found")
    job = Job(
        owner=principal.subject,
        status="queued",
        mode="image",  # approved preview → same path as image jobs (no re-T2I)
        asset_type=body.asset_type,
        prompt=body.prompt,
        input_path=str(path),
        seed=body.seed,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_out(job)


@router.post("/rig", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_rig_job(
    file: UploadFile = File(...),
    seed: int = Form(42),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    suffix = Path(file.filename or "mesh.glb").suffix.lower()
    if suffix not in ALLOWED_MESH:
        raise HTTPException(status_code=400, detail=f"Unsupported mesh type: {suffix}")
    dest = settings.upload_dir / f"{principal.subject.replace(':', '_')}_{uuid.uuid4().hex}{suffix}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    job = Job(
        owner=principal.subject,
        status="queued",
        mode="rig",
        input_path=str(dest),
        seed=seed,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_out(job)


@router.get("/{job_id}/download")
def download_job(
    job_id: int,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None or not _owned(job, principal):
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed" or not job.glb_path or not Path(job.glb_path).is_file():
        raise HTTPException(status_code=409, detail="Asset not ready")
    return FileResponse(
        job.glb_path,
        media_type="model/gltf-binary",
        filename=f"yeetgen_job_{job_id}.glb",
    )


@router.get("/{job_id}/preview")
def preview_job_image(
    job_id: int,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None or not _owned(job, principal):
        raise HTTPException(status_code=404, detail="Job not found")
    path = _preview_image_path(job)
    if path is None:
        raise HTTPException(status_code=404, detail="Preview image not ready")
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, filename=f"yeetgen_job_{job_id}_preview{path.suffix}")


@router.get("/{job_id}/logs")
def get_job_logs(
    job_id: int,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None or not _owned(job, principal):
        raise HTTPException(status_code=404, detail="Job not found")
    path = settings.output_dir / f"job_{job_id}" / "worker.log"
    log_text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    return {"job_id": job_id, "status": job.status, "log": log_text}


def _purge_job_files(job: Job) -> None:
    out = settings.output_dir / f"job_{job.id}"
    if out.is_dir():
        shutil.rmtree(out, ignore_errors=True)
    if job.input_path:
        p = Path(job.input_path)
        # Only delete uploads we own under upload_dir
        try:
            if p.is_file() and settings.upload_dir.resolve() in p.resolve().parents:
                p.unlink(missing_ok=True)
        except Exception:
            pass


@router.delete("/failed")
def delete_failed_jobs(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    q = db.query(Job).filter(Job.status == "failed")
    if not principal.is_admin:
        q = q.filter(Job.owner == principal.subject)
    jobs = q.all()
    deleted = 0
    for job in jobs:
        _purge_job_files(job)
        db.delete(job)
        deleted += 1
    db.commit()
    return {"deleted": deleted}


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_job(
    job_id: int,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None or not _owned(job, principal):
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("failed", "completed"):
        raise HTTPException(status_code=409, detail=f"Cannot retry job in status {job.status}")
    if job.mode in ("image", "rig") and (not job.input_path or not Path(job.input_path).is_file()):
        raise HTTPException(status_code=409, detail="Original input file is missing; create a new job")
    if job.mode == "text" and not (job.prompt or "").strip() and not (
        job.input_path and Path(job.input_path).is_file()
    ):
        raise HTTPException(status_code=409, detail="Missing prompt for text job")

    # Keep outputs so resume can skip finished stages when artifacts exist
    job.status = "queued"
    job.error = None
    job.glb_path = None
    job.started_at = None
    job.finished_at = None
    db.commit()
    db.refresh(job)
    return _job_out(job)


@router.post("/{job_id}/rebake", response_model=JobOut)
def rebake_job(
    job_id: int,
    req: JobRebakeRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Rebake texture projection on existing raw mesh with custom UV warp & rotation offsets."""
    import json

    job = db.get(Job, job_id)
    if job is None or not _owned(job, principal):
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "running":
        raise HTTPException(status_code=409, detail="Cannot rebake while job is actively running")

    out_dir = settings.output_dir / f"job_{job.id}"
    asset_dir = out_dir / "asset"
    asset_dir.mkdir(parents=True, exist_ok=True)

    # Save rebake configuration parameters for the pipeline worker
    rebake_file = asset_dir / "rebake_options.json"
    rebake_file.write_text(json.dumps(req.model_dump(), indent=2))

    # Clean out downstream texture and rigged artifacts so pipeline resumes fresh from mesh_raw.glb
    for f in [
        asset_dir / "mesh.glb",
        asset_dir / "asset_i2tex_shaded.glb",
        asset_dir / "asset_textured.glb",
        asset_dir / "mesh_raw_unwarp.glb",
        asset_dir / "unirig" / "mesh.glb",
    ]:
        if f.is_file():
            f.unlink(missing_ok=True)

    job.status = "queued"
    job.error = None
    job.glb_path = None
    job.started_at = None
    job.finished_at = None
    db.commit()
    db.refresh(job)
    return _job_out(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None or not _owned(job, principal):
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "running":
        raise HTTPException(status_code=409, detail="Stop/wait for running job before deleting")
    _purge_job_files(job)
    db.delete(job)
    db.commit()
    return None
