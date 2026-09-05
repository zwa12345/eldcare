"""/api/v2/player - 流播放 + 字幕

支持 HTTP Range（媒体文件分段传输），前端 vidstack / 原生 video 都能用。
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.logging import logger
from app.models.movie import Movie

router = APIRouter(prefix="/player", tags=["player"])


# ---------- 内部：安全的 Range 响应 ----------

_CHUNK_SIZE = 1024 * 1024  # 1MB


def _parse_range(header: str, file_size: int) -> tuple[int, int] | None:
    """解析 'bytes=start-end'，返回 (start, end) 或 None 表示全文"""
    m = re.match(r"bytes=(\d*)-(\d*)", header.strip())
    if not m:
        return None
    start_s, end_s = m.group(1), m.group(2)
    if not start_s and not end_s:
        return None
    if start_s == "":
        # suffix: 最后 N 字节
        n = int(end_s)
        start = max(0, file_size - n)
        end = file_size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else file_size - 1
    if start >= file_size or end >= file_size or start > end:
        return None
    return start, end


def _file_iterator(path: Path, start: int, end: int):
    with path.open("rb") as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = f.read(min(_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


# ---------- 路由 ----------


@router.head("/stream/{movie_id}")
@router.get("/stream/{movie_id}")
def stream_movie(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """媒体流播放：支持 HTTP Range

    浏览器原生 <video src="..."/> 和 vidstack 都能识别。
    """
    m = db.get(Movie, movie_id)
    if not m or m.status != "active":
        raise HTTPException(status_code=404, detail="movie not found")

    path = Path(m.file_path)
    if not path.exists() or not path.is_file():
        logger.warning(f"stream: file missing: {path}")
        raise HTTPException(status_code=410, detail="media file no longer exists")

    file_size = path.stat().st_size
    # 根据扩展名定 mime
    ext = path.suffix.lower().lstrip(".")
    mime = {
        "mp4": "video/mp4",
        "m4v": "video/mp4",
        "webm": "video/webm",
        "mkv": "video/x-matroska",
        "avi": "video/x-msvideo",
        "mov": "video/quicktime",
        "ts": "video/mp2t",
    }.get(ext, "application/octet-stream")

    range_header = request.headers.get("range") or request.headers.get("Range")
    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": mime,
        "Cache-Control": "public, max-age=3600",
    }

    if range_header:
        rng = _parse_range(range_header, file_size)
        if rng is None:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
        start, end = rng
        length = end - start + 1
        headers = {
            **base_headers,
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(length),
        }
        # HEAD 请求只返头
        if request.method == "HEAD":
            return Response(status_code=206, headers=headers)
        return StreamingResponse(
            _file_iterator(path, start, end),
            status_code=206,
            headers=headers,
            media_type=mime,
        )

    # 无 Range → 全文（慎用大文件）
    headers = {**base_headers, "Content-Length": str(file_size)}
    if request.method == "HEAD":
        return Response(status_code=200, headers=headers)
    return StreamingResponse(
        _file_iterator(path, 0, file_size - 1),
        status_code=200,
        headers=headers,
        media_type=mime,
    )
