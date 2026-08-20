from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import errors
from .db import get_db
from .models import User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise errors.unauthorized("Missing token")
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise errors.unauthorized("Invalid or expired token")

    user_id = int(payload.get("sub", 0))
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise errors.unauthorized("User disabled or not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise errors.forbidden("Admin permission required")
    return user
