"""影片主表

设计参考 pi05-legacy/db-schema/schema.sql 的 movies 表结构，
扩展部分 V2 字段。全字段对应 Pydantic schema 在 api/library.py。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)

    # 标题（双标题，对齐 pi05 旧版字段）
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    title_en: Mapped[Optional[str]] = mapped_column(String(512))

    # 元数据
    year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(16))   # 4K/1080p/720p
    source: Mapped[Optional[str]] = mapped_column(String(32))       # WEB-DL/BluRay/HDTV
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    poster_url: Mapped[Optional[str]] = mapped_column(String(1024))
    backdrop_url: Mapped[Optional[str]] = mapped_column(String(1024))
    overview: Mapped[Optional[str]] = mapped_column(Text)
    rating: Mapped[Optional[float]] = mapped_column(Float)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer)
    category: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    tags: Mapped[Optional[str]] = mapped_column(Text)              # JSON array

    # 文件信息
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    video_codec: Mapped[Optional[str]] = mapped_column(String(16))  # h264/h265/av1
    audio_codec: Mapped[Optional[str]] = mapped_column(String(32))  # aac/dts/truehd
    container: Mapped[Optional[str]] = mapped_column(String(16))    # mkv/mp4
    has_subtitle: Mapped[bool] = mapped_column(Boolean, default=False)

    # 演员 / 类型 / 国家（用 string 存，匹配 pi05 旧字段习惯）
    director: Mapped[Optional[str]] = mapped_column(String(512))
    actors: Mapped[Optional[str]] = mapped_column(Text)
    country: Mapped[Optional[str]] = mapped_column(String(128))
    genre: Mapped[Optional[str]] = mapped_column(String(256))

    # 下载来源（兼容 pi05 magnet / status）
    magnet: Mapped[Optional[str]] = mapped_column(Text)
    download_status: Mapped[str] = mapped_column(String(32), default="none")  # none/local/external/pending

    # 软删除 / 状态
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active/deleted/pending

    # 统计
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # 时间戳
    added_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Movie #{self.id} {self.title!r}>"
