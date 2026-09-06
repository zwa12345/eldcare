"""/api/v2/admin - 管理操作（手动扫描等）

注意：这些是运维类接口，家庭内网使用。若需暴露到外网应先加鉴权。
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.logging import logger
from app.services.scanner import scan_movies

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/scan")
def admin_scan(db: Session = Depends(get_db)) -> dict:
    """手动触发一次媒体目录扫描（幂等入库）"""
    logger.info("POST /api/v2/admin/scan invoked")
    result = scan_movies(db)
    return asdict(result)
