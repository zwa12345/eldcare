"""下载任务（aria2 gid 关联）"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DownloadTask(Base):
    __tablename__ = "download_tasks"

    gid: Mapped[str] = mapped_column(String(64), primary_key=True)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    save_path: Mapped[Optional[str]] = mapped_column(String(1024))
    filename: Mapped[Optional[str]] = mapped_column(String(512))

    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    done_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    download_speed: Mapped[int] = mapped_column(BigInteger, default=0)  # B/s

    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    # queued / active / paused / complete / error / removed
    error: Mapped[Optional[str]] = mapped_column(Text)

    # 关联到影片（下载完成后回填）
    movie_id: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
