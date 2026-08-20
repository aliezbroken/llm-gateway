from pydantic import BaseModel


class UsageLogOut(BaseModel):
    id: int
    ts: object = None
    user_id: int
    token_id: int
    token_name: str
    client_ip: str
    model: str
    endpoint: str
    request_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    quota_cost: int
    latency_ms: float
    status: str
    error_code: str

    model_config = {"from_attributes": True}
