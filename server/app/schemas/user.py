from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = "user"  # admin | user
    quota: int = 0
    max_concurrency: int = 0  # 0 = unlimited
    remark: str = ""


class UserUpdate(BaseModel):
    status: str | None = None  # active | disabled
    remark: str | None = None
    max_concurrency: int | None = None
    password: str | None = None  # reset password if provided


class QuotaGrant(BaseModel):
    delta: int  # positive = add, negative = deduct
    reason: str = ""


class QuotaLedgerOut(BaseModel):
    id: int
    ts: object = None
    user_id: int
    operator_id: int
    delta: int
    balance_after: int
    reason: str

    model_config = {"from_attributes": True}
