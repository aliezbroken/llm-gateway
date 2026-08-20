from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "llm-gateway"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = f"sqlite:///{BASE_DIR / 'gateway.db'}"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # 上游 vLLM 地址：默认占位 localhost，实际地址用环境变量 UPSTREAM_URL 或后台系统设置配置
    upstream_url: str = "http://127.0.0.1:8000"
    health_check_interval: int = 30

    # 前端静态目录（vite build 产物），不存在时跳过静态托管（纯 API 模式）
    static_dir: str = str(BASE_DIR.parent / "web" / "dist")

    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin123"
    seed_admin_quota: int = 1_000_000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
