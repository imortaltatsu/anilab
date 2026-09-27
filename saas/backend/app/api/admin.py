from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_admin
from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.db import AllowedPassword, Job, SessionLocal, get_db
from app.models.schemas import AllowedPasswordCreate, AllowedPasswordOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/passwords", response_model=list[AllowedPasswordOut])
def list_passwords(
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(AllowedPassword).order_by(AllowedPassword.id.desc()).all()


@router.post("/passwords", response_model=AllowedPasswordOut, status_code=status.HTTP_201_CREATED)
def add_password(
    body: AllowedPasswordCreate,
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    for row in db.query(AllowedPassword).filter(AllowedPassword.active.is_(True)).all():
        if verify_password(body.password, row.password_hash):
            raise HTTPException(status_code=409, detail="Password already allowlisted")
    row = AllowedPassword(
        label=body.label.strip() or "access",
        password_hash=hash_password(body.password),
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/passwords/{password_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_password(
    password_id: int,
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.get(AllowedPassword, password_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return None


def _job_log_path(job_id: int) -> Path:
    return settings.output_dir / f"job_{job_id}" / "worker.log"


@router.get("/jobs/{job_id}/logs")
def get_job_logs(
    job_id: int,
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = _job_log_path(job_id)
    if not path.is_file():
        return {"job_id": job_id, "status": job.status, "log": ""}
    return {
        "job_id": job_id,
        "status": job.status,
        "log": path.read_text(encoding="utf-8", errors="replace"),
    }


@router.get("/jobs/{job_id}/logs/stream")
async def stream_job_logs(
    job_id: int,
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """SSE live tail of worker.log for admin."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    path = _job_log_path(job_id)

    async def event_gen():
        import asyncio

        pos = 0
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            pos = path.stat().st_size
            for line in text.splitlines():
                yield f"data: {line}\n\n"

        idle = 0
        while idle < 1200:
            await asyncio.sleep(1.0)
            if path.is_file():
                size = path.stat().st_size
                if size > pos:
                    with path.open("rb") as f:
                        f.seek(pos)
                        chunk = f.read()
                    pos = size
                    idle = 0
                    for line in chunk.decode("utf-8", errors="replace").splitlines():
                        yield f"data: {line}\n\n"
                else:
                    idle += 1
                    if idle % 5 == 0:
                        yield ": ping\n\n"
            else:
                idle += 1

            s = SessionLocal()
            try:
                j = s.get(Job, job_id)
                if j and j.status in ("completed", "failed") and idle > 2:
                    yield f"data: [status] {j.status}\n\n"
                    break
            finally:
                s.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")
