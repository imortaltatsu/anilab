from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_current_principal
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.models.db import AllowedPassword, get_db
from app.models.schemas import MeOut, PasswordLoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: PasswordLoginRequest, db: Session = Depends(get_db)):
    """Password-only login. Admin password → admin JWT; allowlisted password → user JWT."""
    password = body.password

    if password == settings.admin_password:
        token = create_access_token("admin", extra={"role": "admin"})
        return TokenResponse(access_token=token, role="admin")

    rows = db.query(AllowedPassword).filter(AllowedPassword.active.is_(True)).all()
    for row in rows:
        if verify_password(password, row.password_hash):
            token = create_access_token(f"pwd:{row.id}", extra={"role": "user"})
            return TokenResponse(access_token=token, role="user")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_current_principal)):
    return MeOut(subject=principal.subject, role=principal.role)
