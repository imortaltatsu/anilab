from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    subject: str
    role: str  # user | admin

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def get_current_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        sub = payload.get("sub")
        role = payload.get("role", "user")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        if role not in ("user", "admin"):
            role = "user"
        return Principal(subject=str(sub), role=str(role))
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if not principal.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return principal
