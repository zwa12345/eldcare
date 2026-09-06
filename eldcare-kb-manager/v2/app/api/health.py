"""/api/v2/health - 健康检查"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.api.schemas import HealthOut
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.logging import logger

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthOut)
def health(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> HealthOut:
    """健康检查：DB 连通 + 关键路径存在"""
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.exception("health: db check failed")
        db_status = f"error: {type(e).__name__}"

    return HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        version=__version__,
        instance_id=settings.instance_id,
        node_role=settings.node_role,
        db=db_status,
        movies_dir_exists=settings.movies_dir.exists(),
        db_path=str(settings.db_path),
        movies_dir=str(settings.movies_dir),
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/version")
def version(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "version": __version__,
        "instance_id": settings.instance_id,
        "node_role": settings.node_role,
    }
