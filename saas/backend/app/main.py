from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, jobs
from app.core.config import settings
from app.models.db import init_db
from app.services.worker import worker


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    worker.start()
    yield
    worker.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": settings.app_name,
        "gpus": settings.gpu_ids,
        "max_concurrent_jobs": settings.max_concurrent_jobs,
    }
