from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import get_current_user
from ...models import User
from ...schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, UserOut
from . import service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    token, user = service.authenticate_and_issue_token(db, req)
    return LoginResponse(token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.put("/password")
def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.change_password(db, user, req)
    return {"message": "ok"}
