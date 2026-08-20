from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import get_current_user
from ...errors import forbidden
from ...models import User
from ...schemas.log import UsageLogOut
from ..tokens.service import get_scoped_user_id
from . import service

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def list_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = Query(None),
    userId: int | None = Query(None),
    tokenId: int | None = Query(None),
    model: str = "",
    status: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope_id = get_scoped_user_id(user, userId)
    rows, total = service.list_logs(
        db, page=page, size=size, from_ts=from_, to_ts=to,
        user_id=scope_id, token_id=tokenId, model=model, status=status,
        scope_user_id=scope_id,
    )
    return {
        "items": [UsageLogOut.model_validate(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/{log_id}")
def get_log(log_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    log = service.get_log(db, log_id)
    scope_id = get_scoped_user_id(user, None)
    if scope_id is not None and log.user_id != scope_id:
        raise forbidden("Cannot view others' log")
    return UsageLogOut.model_validate(log)
