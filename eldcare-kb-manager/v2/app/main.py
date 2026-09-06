"""FastAPI 入口"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import admin, health, library, player
from app.core.config import get_settings
from app.core.db import init_db
from app.core.logging import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    setup_logging()
    settings = get_settings()
    logger.info(f"=== eldcare-kb-manager v{__version__} ===")
    logger.info(f"role={settings.node_role} instance={settings.instance_id}")
    logger.info(f"data_dir={settings.data_dir}")
    init_db()
    logger.info("db initialized")

    # 确保静态目录存在
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)

    yield
    logger.info("=== shutdown ===")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Eldcare KB Manager",
        description="家庭影院 V2 — 媒体库、播放器、下载引擎、TMDB 元数据",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS（家庭内网可以宽松些）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 路由
    app.include_router(health.router, prefix="/api/v2")
    app.include_router(library.router, prefix="/api/v2")
    app.include_router(player.router, prefix="/api/v2")
    app.include_router(admin.router, prefix="/api/v2")

    # 静态资源（CSS / JS / icons）
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # PWA manifest
    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        return FileResponse(static_dir / "manifest.webmanifest", media_type="application/manifest+json")

    # service worker
    @app.get("/sw.js", include_in_schema=False)
    def sw():
        return FileResponse(static_dir / "sw.js", media_type="application/javascript")

    # SPA 入口
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index():
        return FileResponse(static_dir / "index.html", media_type="text/html")

    return app


# 暴露给 uvicorn: uvicorn app.main:app
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
