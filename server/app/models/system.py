from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class QuotaLedger(Base):
    __tablename__ = "quota_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    operator_id: Mapped[int] = mapped_column(Integer, default=0)  # 0 = system
    delta: Mapped[int] = mapped_column(BigInteger, nullable=False)  # +add / -deduct
    balance_after: Mapped[int] = mapped_column(BigInteger, default=0)
    reason: Mapped[str] = mapped_column(String(255), default="")
