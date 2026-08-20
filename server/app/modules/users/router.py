from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import require_admin
from ...errors import not_found
from ...models import QuotaLedger, User
from ...schemas.user import QuotaGrant, QuotaLedgerOut, UserCreate, UserUpdate
from . import service

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=1000),
    keyword: str = "",
    role: str = "",
    status: str = "",
    db: Session = Depends(get_db),
):
    users, total = service.list_users(db, page, size, keyword, role, status)
    return {"items": users, "total": total, "page": page, "size": size}


@router.post("")
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    user = service.create_user(db, data)
    return user


@router.put("/{user_id}")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    return service.update_user(db, user_id, data)


@router.delete("/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    service.delete_user(db, user_id, operator_id=admin.id)
    return {"message": "ok"}


@router.post("/{user_id}/quota")
def grant_quota(user_id: int, data: QuotaGrant, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = service.get_user(db, user_id)
    return service.grant_quota(db, target, operator_id=admin.id, data=data)


@router.get("/{user_id}/ledger")
def list_ledger(
    user_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    service.get_user(db, user_id)
    rows, total = service.list_ledger(db, user_id, page, size)
    return {"items": [QuotaLedgerOut.model_validate(r) for r in rows], "total": total, "page": page, "size": size}
