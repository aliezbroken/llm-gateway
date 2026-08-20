from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ... import errors
from ...models import QuotaLedger, UsageLog, User
from ...security import hash_password
from ...schemas.user import QuotaGrant, UserCreate, UserUpdate


def list_users(db: Session, page: int, size: int, keyword: str, role: str, status: str) -> tuple[list[User], int]:
    q = db.query(User)
    if keyword:
        q = q.filter(or_(User.username.like(f"%{keyword}%"), User.remark.like(f"%{keyword}%")))
    if role:
        q = q.filter(User.role == role)
    if status:
        q = q.filter(User.status == status)
    total = q.count()
    users = q.order_by(User.id.desc()).offset((page - 1) * size).limit(size).all()
    stats = get_users_stats(db, [u.id for u in users])
    for u in users:
        u.consumed = stats.get(u.id, {}).get("consumed", 0)
        u.request_count = stats.get(u.id, {}).get("request_count", 0)
    return users, total


def get_users_stats(db: Session, user_ids: list[int]) -> dict[int, dict]:
    """Per-user actual consumption (quota_cost) and request count."""
    if not user_ids:
        return {}
    rows = (
        db.query(UsageLog.user_id, func.count(UsageLog.id), func.coalesce(func.sum(UsageLog.quota_cost), 0))
        .filter(UsageLog.user_id.in_(user_ids))
        .group_by(UsageLog.user_id)
        .all()
    )
    return {uid: {"request_count": int(cnt), "consumed": int(cost)} for uid, cnt, cost in rows}


def create_user(db: Session, data: UserCreate) -> User:
    if db.query(User).filter(User.username == data.username).first():
        raise errors.parameter_error("Username already exists")
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        role=data.role,
        quota=data.quota,
        max_concurrency=data.max_concurrency,
        remark=data.remark,
    )
    db.add(user)
    db.flush()
    if data.quota != 0:
        db.add(QuotaLedger(user_id=user.id, operator_id=0, delta=data.quota, balance_after=data.quota, reason="init"))
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise errors.not_found("User not found")
    if data.status is not None:
        user.status = data.status
    if data.remark is not None:
        user.remark = data.remark
    if data.max_concurrency is not None:
        user.max_concurrency = data.max_concurrency
    if data.password:
        user.password_hash = hash_password(data.password)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int, operator_id: int = 0) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise errors.not_found("User not found")
    if user.id == operator_id:
        raise errors.parameter_error("不能删除当前登录的账户")
    if user.role == "admin":
        active_admins = db.query(User).filter(User.role == "admin", User.status == "active").count()
        if active_admins <= 1:
            raise errors.parameter_error("至少保留一个管理员账户")
    db.delete(user)
    db.commit()


def grant_quota(db: Session, target: User, operator_id: int, data: QuotaGrant) -> User:
    target.quota += data.delta
    db.add(
        QuotaLedger(
            user_id=target.id,
            operator_id=operator_id,
            delta=data.delta,
            balance_after=target.quota,
            reason=data.reason or "grant",
        )
    )
    db.commit()
    db.refresh(target)
    return target


def list_ledger(db: Session, user_id: int, page: int, size: int) -> tuple[list[QuotaLedger], int]:
    q = db.query(QuotaLedger).filter(QuotaLedger.user_id == user_id)
    total = q.count()
    rows = q.order_by(QuotaLedger.id.desc()).offset((page - 1) * size).limit(size).all()
    return rows, total


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise errors.not_found("User not found")
    return user
