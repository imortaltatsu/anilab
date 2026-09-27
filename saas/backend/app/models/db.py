from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


class AllowedPassword(Base):
    """Passwords that can mint a user JWT (hashed at rest)."""

    __tablename__ = "allowed_passwords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120), default="access")
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # JWT subject that owns the job: "admin" or "pwd:<id>"
    owner: Mapped[str] = mapped_column(String(64), index=True, default="anon")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    # image | text | rig
    mode: Mapped[str] = mapped_column(String(16), default="image")
    # character | prop — props skip UniRig; same ~35k face target as characters
    asset_type: Mapped[str] = mapped_column(String(16), default="character")
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    output_dir: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    glb_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed: Mapped[int] = mapped_column(Integer, default=42)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from sqlalchemy import text

    from app.core.security import hash_password

    Base.metadata.create_all(bind=engine)
    # Soft-migrate SQLite: add asset_type if missing on older DBs
    with engine.begin() as conn:
        if settings.database_url.startswith("sqlite"):
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(jobs)")).fetchall()}
            if "asset_type" not in cols:
                conn.execute(
                    text("ALTER TABLE jobs ADD COLUMN asset_type VARCHAR(16) DEFAULT 'character'")
                )

    db = SessionLocal()
    try:
        # Fresh schema: if legacy users table exists alone, passwords table is new.
        count = db.query(AllowedPassword).count()
        if count == 0 and settings.bootstrap_password:
            db.add(
                AllowedPassword(
                    label="default",
                    password_hash=hash_password(settings.bootstrap_password),
                    active=True,
                )
            )
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
