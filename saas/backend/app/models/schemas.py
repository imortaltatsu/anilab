from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer


class PasswordLoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str  # user | admin


class MeOut(BaseModel):
    subject: str
    role: str


class AllowedPasswordCreate(BaseModel):
    password: str = Field(min_length=4, max_length=256)
    label: str = Field(default="access", min_length=1, max_length=120)


class AllowedPasswordOut(BaseModel):
    id: int
    label: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _ser_created(self, value: datetime) -> str:
        return _iso_utc(value)


class JobCreateText(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    seed: int = 42
    asset_type: str = Field(default="character", pattern="^(character|prop)$")


class TposePreviewOut(BaseModel):
    preview_url: str
    filename: str
    seed: int
    prompt: str


class JobFromTposePreview(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    seed: int = 42
    filename: str = Field(min_length=8, max_length=256)
    asset_type: str = Field(default="character", pattern="^(character|prop)$")


class JobOut(BaseModel):
    id: int
    status: str
    mode: str
    asset_type: str = "character"
    prompt: str | None
    glb_path: str | None
    error: str | None
    seed: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    download_url: str | None = None
    preview_url: str | None = None

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "started_at", "finished_at")
    def _ser_times(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return _iso_utc(value)


class JobRebakeRequest(BaseModel):
    rotation_yaw: float = Field(default=0.0, ge=-360.0, le=360.0)
    rotation_pitch: float = Field(default=0.0, ge=-90.0, le=90.0)
    uv_size: int = Field(default=2048)
    inpaint_mode: str = Field(default="uv", pattern="^(uv|view)$")
    steps: int = Field(default=50, ge=10, le=100)
    guidance: float = Field(default=4.0, ge=1.0, le=15.0)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")
