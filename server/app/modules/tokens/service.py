import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from ... import errors
from ...models import ApiToken, UsageLog, User
from ...security import generate_api_key, hash_api_key
from ...schemas.token import TokenCreate, TokenUpdate


def list_tokens(db: Session, user_id: int | None) -> list[ApiToken]:
    q = db.query(ApiToken)
    if user_id is not None:
        q = q.filter(ApiToken.user_id == user_id)
    return q.order_by(ApiToken.id.desc()).all()


def create_token(db: Session, user: User, data: TokenCreate) -> tuple[ApiToken, str]:
    api_key = generate_api_key()
    token = ApiToken(
        user_id=user.id,
        name=data.name,
        key_hash=hash_api_key(api_key),
        quota_limit=data.quota_limit,
        allowed_ips=json.dumps(data.allowed_ips),
        max_concurrency=data.max_concurrency,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, api_key


def update_token(db: Session, token_id: int, user: User, data: TokenUpdate, admin: bool = False) -> ApiToken:
    token = db.get(ApiToken, token_id)
    if token is None:
        raise errors.not_found("Token not found")
    if not admin and token.user_id != user.id:
        raise errors.forbidden("Cannot operate others' token")
    if data.name is not None:
        token.name = data.name
    if data.status is not None:
        token.status = data.status
    if data.quota_limit is not None:
        token.quota_limit = data.quota_limit
    if data.allowed_ips is not None:
        token.allowed_ips = json.dumps(data.allowed_ips)
    if data.max_concurrency is not None:
        token.max_concurrency = data.max_concurrency
    db.commit()
    db.refresh(token)
    return token


def delete_token(db: Session, token_id: int, user: User, admin: bool = False) -> None:
    token = db.get(ApiToken, token_id)
    if token is None:
        raise errors.not_found("Token not found")
    if not admin and token.user_id != user.id:
        raise errors.forbidden("Cannot delete others' token")
    db.delete(token)
    db.commit()


# ---- used by gateway ----

def resolve_token_by_key(db: Session, api_key: str) -> ApiToken | None:
    return db.query(ApiToken).filter(ApiToken.key_hash == hash_api_key(api_key)).first()


def get_token_used_quota(db: Session, token_id: int) -> int:
    return db.query(func.coalesce(func.sum(UsageLog.quota_cost), 0)).filter(UsageLog.token_id == token_id).scalar() or 0


def validate_token(db: Session, api_key: str, client_ip: str) -> ApiToken:
    """Gateway-facing validation: existence, status, IP whitelist, quota limit."""
    token = resolve_token_by_key(db, api_key)
    if token is None or token.status != "active":
        raise errors.raise_http(401, errors.ErrorCode.INVALID_API_KEY, "Invalid API key", "invalid_request_error")
    if token.allowed_ips and token.allowed_ips != "[]":
        allowed = set(json.loads(token.allowed_ips))
        if client_ip not in allowed:
            raise errors.raise_http(403, errors.ErrorCode.IP_NOT_ALLOWED, "IP not allowed", "invalid_request_error")
    if token.quota_limit is not None:
        used = get_token_used_quota(db, token.id)
        if used >= token.quota_limit:
            raise errors.raise_http(402, errors.ErrorCode.INSUFFICIENT_QUOTA, "Token quota limit reached", "invalid_request_error")
    return token


def get_scoped_user_id(user: User, query_user_id: int | None) -> int | None:
    """users/tokens/logs scope helper: admin may pass userId, normal user forced to self."""
    if user.role == "admin":
        return query_user_id
    return user.id


def get_usernames(db: Session, user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = db.query(User.id, User.username).filter(User.id.in_(user_ids)).all()
    return {uid: name for uid, name in rows}


def get_username(db: Session, user_id: int) -> str:
    u = db.get(User, user_id)
    return u.username if u else ""
