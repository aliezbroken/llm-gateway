from pydantic import BaseModel, Field


class SystemSettingsOut(BaseModel):
    upstream_url: str
    model_ratios: dict[str, dict[str, float]] = {}  # {"model": {"prompt": 1.0, "completion": 1.0}}


class SystemSettingsUpdate(BaseModel):
    upstream_url: str | None = None
    model_ratios: dict[str, dict[str, float]] | None = Field(default=None, description='{"model": {"prompt": x, "completion": y}}')


class HealthOut(BaseModel):
    online: bool
    latency_ms: float = 0.0
    last_check: object = None
    message: str = ""
