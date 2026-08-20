import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import get_current_user
from ...errors import forbidden, not_found
from ...models import ApiToken, User
from ...schemas.token import TokenCreate, TokenCreateResponse, TokenOut, TokenUpdate
from . import service

router = APIRouter(prefix="/api/tokens", tags=["tokens"])


def _to_out(token, used_quota: int, username: str = "") -> TokenOut:
    out = TokenOut(
        id=token.id,
        user_id=token.user_id,
        username=username,
        name=token.name,
        status=token.status,
        quota_limit=token.quota_limit,
        allowed_ips=json.loads(token.allowed_ips) if token.allowed_ips else [],
        max_concurrency=token.max_concurrency,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
    )
    out.key_prefix = "sk-****" + token.key_hash[:6]
    out.used_quota = used_quota
    return out


@router.get("")
def list_tokens(
    userId: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope_id = service.get_scoped_user_id(user, userId)
    tokens = service.list_tokens(db, scope_id)
    names = service.get_usernames(db, [t.user_id for t in tokens])
    items = [_to_out(t, service.get_token_used_quota(db, t.id), names.get(t.user_id, "")) for t in tokens]
    return {"items": items}


@router.post("", response_model=TokenCreateResponse)
def create_token(data: TokenCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token, api_key = service.create_token(db, user, data)
    return TokenCreateResponse(token=_to_out(token, 0, user.username), api_key=api_key)


@router.put("/{token_id}")
def update_token(token_id: int, data: TokenUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token = service.update_token(db, token_id, user, data, admin=user.role == "admin")
    return _to_out(token, service.get_token_used_quota(db, token.id), service.get_username(db, token.user_id))


@router.delete("/{token_id}")
def delete_token(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.delete_token(db, token_id, user, admin=user.role == "admin")
    return {"message": "ok"}


@router.get("/{token_id}/usage")
def token_usage(token_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token = db.get(ApiToken, token_id)
    if token is None:
        not_found("Token not found")
    if user.role != "admin" and token.user_id != user.id:
        forbidden("Cannot view others' token")
    return {"used_quota": service.get_token_used_quota(db, token.id), "quota_limit": token.quota_limit}
