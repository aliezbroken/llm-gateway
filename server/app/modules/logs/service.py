from sqlalchemy.orm import Session

from ... import errors
from ...models import UsageLog


def list_logs(
    db: Session,
    *,
    page: int,
    size: int,
    from_ts=None,
    to_ts=None,
    user_id: int | None = None,
    token_id: int | None = None,
    model: str = "",
    status: str = "",
    scope_user_id: int | None = None,
) -> tuple[list[UsageLog], int]:
    q = db.query(UsageLog)
    if from_ts is not None:
        q = q.filter(UsageLog.ts >= from_ts)
    if to_ts is not None:
        q = q.filter(UsageLog.ts <= to_ts)
    if user_id is not None:
        q = q.filter(UsageLog.user_id == user_id)
    if scope_user_id is not None:
        q = q.filter(UsageLog.user_id == scope_user_id)
    if token_id is not None:
        q = q.filter(UsageLog.token_id == token_id)
    if model:
        q = q.filter(UsageLog.model == model)
    if status:
        q = q.filter(UsageLog.status == status)
    total = q.count()
    rows = q.order_by(UsageLog.id.desc()).offset((page - 1) * size).limit(size).all()
    return rows, total


def get_log(db: Session, log_id: int) -> UsageLog:
    log = db.get(UsageLog, log_id)
    if log is None:
        raise errors.not_found("Log not found")
    return log
