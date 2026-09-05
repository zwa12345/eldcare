"""用户表（简化版，家庭场景一个用户就够）

实际可能一台设备一个 user（用 device_fingerprint 区分）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256))
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(256), index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username}>"
