from sqlalchemy.orm import Session

from ... import errors
from ...models import User
from ...security import create_access_token, hash_password, verify_password
from ...schemas.auth import ChangePasswordRequest, LoginRequest


def authenticate_and_issue_token(db: Session, req: LoginRequest) -> tuple[str, User]:
    user = db.query(User).filter(User.username == req.username).first()
    if user is None or not verify_password(req.password, user.password_hash):
        raise errors.unauthorized("Invalid username or password")
    if user.status != "active":
        raise errors.unauthorized("User is disabled")
    token = create_access_token(user.id, user.username, user.role)
    return token, user


def change_password(db: Session, user: User, req: ChangePasswordRequest) -> None:
    if not verify_password(req.old_password, user.password_hash):
        raise errors.parameter_error("Old password is incorrect")
    user.password_hash = hash_password(req.new_password)
    db.commit()
