from pydantic import BaseModel, Field


class TokenCreate(BaseModel):
    name: str = Field(default="default", max_length=64)
    quota_limit: int | None = None  # NULL/0 = unlimited
    allowed_ips: list[str] = []
    max_concurrency: int = 0  # 0 = unlimited


class TokenUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    quota_limit: int | None = None
    allowed_ips: list[str] | None = None
    max_concurrency: int | None = None


class TokenOut(BaseModel):
    id: int
    user_id: int
    username: str = ""  # owner username
    name: str
    key_prefix: str = ""  # sk-xxxx… masked
    status: str
    quota_limit: int | None
    allowed_ips: list[str] = []
    max_concurrency: int
    used_quota: int = 0
    created_at: object = None
    last_used_at: object = None

    model_config = {"from_attributes": True}


class TokenCreateResponse(BaseModel):
    token: TokenOut
    api_key: str  # plaintext shown once
