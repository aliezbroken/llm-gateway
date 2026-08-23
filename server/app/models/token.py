from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), default="default")
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active | disabled
    quota_limit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # NULL/0 = unlimited
    allowed_ips: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    max_concurrency: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
