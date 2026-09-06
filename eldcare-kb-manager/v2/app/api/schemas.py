"""Pydantic Schemas 集中处"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MovieOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    title_en: Optional[str] = None
    year: Optional[int] = None
    resolution: Optional[str] = None
    source: Optional[str] = None
    tmdb_id: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    overview: Optional[str] = None
    rating: Optional[float] = None
    duration_sec: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    file_size: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    container: Optional[str] = None
    has_subtitle: bool = False
    director: Optional[str] = None
    actors: Optional[str] = None
    country: Optional[str] = None
    genre: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    is_favorite: bool = False
    added_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MovieListResponse(BaseModel):
    items: list[MovieOut]
    total: int
    page: int
    size: int


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    icon: Optional[str] = None
    sort_order: int = 0


class StatsOut(BaseModel):
    total_movies: int = 0
    total_categories: int = 0
    total_size_bytes: int = 0
    total_duration_sec: int = 0
    favorite_count: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_resolution: dict[str, int] = Field(default_factory=dict)


class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    instance_id: str
    node_role: str
    db: str = "ok"
    movies_dir_exists: bool
    db_path: str
    movies_dir: str
    timestamp: datetime
