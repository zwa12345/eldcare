"""/api/v2/library - 媒体库浏览/搜索/分类"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    CategoryOut,
    MovieListResponse,
    MovieOut,
    StatsOut,
)
from app.core.db import get_db
from app.core.logging import logger
from app.models.category import Category
from app.models.movie import Movie

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/movies", response_model=MovieListResponse)
def list_movies(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    category: str | None = Query(None, description="按分类 slug 过滤"),
    q: str | None = Query(None, description="搜索关键字（title / title_en / actors / director）"),
    sort: str = Query("added_at", pattern="^(added_at|year|rating|title)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    is_favorite: bool | None = None,
) -> MovieListResponse:
    stmt = select(Movie).where(Movie.status == "active")

    if category:
        stmt = stmt.where(Movie.category == category)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Movie.title.ilike(like),
                Movie.title_en.ilike(like),
                Movie.actors.ilike(like),
                Movie.director.ilike(like),
                Movie.overview.ilike(like),
            )
        )

    if is_favorite is not None:
        stmt = stmt.where(Movie.is_favorite == is_favorite)

    # 排序
    col = getattr(Movie, sort)
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc())

    # 总数
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    # 分页
    stmt = stmt.offset((page - 1) * size).limit(size)
    items = db.execute(stmt).scalars().all()

    return MovieListResponse(
        items=[MovieOut.model_validate(m) for m in items],
        total=total,
        page=page,
        size=size,
    )


@router.get("/movies/{movie_id}", response_model=MovieOut)
def get_movie(movie_id: int, db: Session = Depends(get_db)) -> MovieOut:
    m = db.get(Movie, movie_id)
    if not m or m.status != "active":
        raise HTTPException(status_code=404, detail="movie not found")
    return MovieOut.model_validate(m)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryOut]:
    rows = db.execute(
        select(Category).order_by(Category.sort_order.asc(), Category.id.asc())
    ).scalars().all()
    return [CategoryOut.model_validate(c) for c in rows]


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)) -> StatsOut:
    """库统计：总数 / 分类 / 分辨率 / 大小 / 时长"""
    base = select(Movie).where(Movie.status == "active")

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    total_size = db.execute(
        select(func.coalesce(func.sum(Movie.file_size), 0))
        .where(Movie.status == "active")
    ).scalar_one()

    total_duration = db.execute(
        select(func.coalesce(func.sum(Movie.duration_sec), 0))
        .where(Movie.status == "active")
    ).scalar_one()

    fav_count = db.execute(
        select(func.count(Movie.id)).where(
            Movie.status == "active",
            Movie.is_favorite.is_(True),
        )
    ).scalar_one()

    # 按分类
    cat_rows = db.execute(
        select(Movie.category, func.count(Movie.id))
        .where(Movie.status == "active")
        .group_by(Movie.category)
    ).all()
    by_category = {(c or "未分类"): n for c, n in cat_rows}

    # 按分辨率
    res_rows = db.execute(
        select(Movie.resolution, func.count(Movie.id))
        .where(Movie.status == "active")
        .group_by(Movie.resolution)
    ).all()
    by_resolution = {(r or "未知"): n for r, n in res_rows}

    return StatsOut(
        total_movies=total,
        total_categories=db.execute(select(func.count(Category.id)).where(Category.id.is_not(None))).scalar_one(),
        total_size_bytes=int(total_size or 0),
        total_duration_sec=int(total_duration or 0),
        favorite_count=fav_count,
        by_category=by_category,
        by_resolution=by_resolution,
    )
