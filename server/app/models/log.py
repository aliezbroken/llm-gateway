from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class UsageLog(Base):
    __tablename__ = "usage_logs"
    __table_args__ = (Index("ix_usage_logs_ts", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    token_id: Mapped[int] = mapped_column(ForeignKey("api_tokens.id"), index=True, nullable=False)
    token_name: Mapped[str] = mapped_column(String(64), default="")
    client_ip: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128), default="", index=True)
    endpoint: Mapped[str] = mapped_column(String(128), default="")
    request_id: Mapped[str] = mapped_column(String(64), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    quota_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="ok", index=True)  # ok | rejected | ...
    error_code: Mapped[str] = mapped_column(String(32), default="")
