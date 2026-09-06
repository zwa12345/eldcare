"""媒体目录扫描器

功能：
- 递归扫描 settings.movies_dir 下的视频文件
- 用正则解析文件名 → title/year/resolution/source（DESIGN §7.1）
- 用 ffprobe 探测时长/分辨率/编码（失败自动降级，不中断）
- ORM 幂等入库（file_path 唯一，已存在则跳过/补空字段）

设计约定：
- 所有写操作走 SQLAlchemy ORM（Python default 兜底），禁止裸 sqlite3 INSERT
- 单文件独立 commit，单文件失败不污染整批
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import logger
from app.models.movie import Movie

# 支持的视频扩展（对齐 player.py 的 mime 表）
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".ts", ".m4v", ".webm"}

# 忽略小于该字节数的文件（防碎片/空文件）
_MIN_SIZE = 10 * 1024 * 1024  # 10MB

# ffprobe 参数（JSON 输出）
_FFPROBE = ["ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams"]


# ---------------------------------------------------------------------------
# 文件名解析
# ---------------------------------------------------------------------------

# DESIGN §7.1 正则模板，按优先级匹配
# 说明：分隔符兼容 . / 空格 / 括号；分辨率/来源为关键词，不强制前置点，
# 避免「year 后分隔符已吃掉点、后续再找点」的歧义。
_PATTERNS = [
    # 1. 名称.年份.来源.分辨率（如 长安三万里.2023.WEB-DL.1080p.mkv）
    re.compile(
        r"^(?P<title>.+?)[\.\s]+(?P<year>\d{4})[\.\s]+"
        r"(?P<source>WEB-?DL|BluRay|HDTV|REMUX|HD)[\.\s]+"
        r"(?P<res>\d+p|UHD|4K)\b",
        re.IGNORECASE,
    ),
    # 2. 名称.年份.分辨率（如 长安三万里.2023.1080p.mkv）
    re.compile(
        r"^(?P<title>.+?)[\.\s]+(?P<year>\d{4})[\.\s]+.*?"
        r"(?P<res>\d+p|UHD|4K)\b",
        re.IGNORECASE,
    ),
    # 3. 名称 (年份).分辨率（如 长安三万里 (2023).1080p.mkv）
    re.compile(
        r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*[\.\s]*.*?"
        r"(?P<res>\d+p|UHD|4K)\b",
        re.IGNORECASE,
    ),
]

# 分辨率归一化：ffprobe 高度 → 展示分辨率
_HEIGHT_TO_RES = {
    2160: "4K",
    1080: "1080p",
    720: "720p",
    480: "480p",
    576: "576p",
}

# 中文字符检测（用于启发式把英文标题填到 title_en）
_RE_CJK = re.compile(r"[\u4e00-\u9fff]")


def _clean(text: str) -> str:
    """把 . _ 替换为空格，压缩空白，去首尾"""
    text = re.sub(r"[._]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class ParsedMeta:
    """文件名解析结果"""
    title: str
    title_en: Optional[str] = None
    year: Optional[int] = None
    resolution: Optional[str] = None
    source: Optional[str] = None


def parse_filename(path: Path) -> ParsedMeta:
    """解析视频文件名 → 结构化元数据

    按 _PATTERNS 顺序匹配；全部失败则取文件名去后缀为 title。
    """
    stem = path.stem  # 去后缀

    for pat in _PATTERNS:
        m = pat.match(stem)
        if m:
            title_raw = _clean(m.group("title"))
            title_en = None
            if not _RE_CJK.search(title_raw):
                title_en = title_raw  # 纯英文标题，同时作 title_en
            res_raw = m.group("res").lower()
            resolution = {"4k": "4K", "uhd": "4K", "2160p": "4K"}.get(
                res_raw, res_raw
            )
            source_raw = (m.groupdict().get("source") or "").upper().replace("-", "-")
            source = source_raw or None
            # source 若含 "WEB" → WEB-DL 规整
            if source:
                if "WEB" in source:
                    source = "WEB-DL"
                elif "BLURAY" in source:
                    source = "BluRay"
                elif "REMUX" in source:
                    source = "REMUX"
                elif "HDTV" in source:
                    source = "HDTV"
                else:
                    source = source
            return ParsedMeta(
                title=title_raw,
                title_en=title_en,
                year=int(m.group("year")),
                resolution=resolution,
                source=source,
            )

    # fallback：整个文件名作标题
    title = _clean(stem)
    return ParsedMeta(title=title)


# ---------------------------------------------------------------------------
# ffprobe 探测（可降级）
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """媒体探测结果（可全为空 = 探测失败/无 ffprobe）"""
    duration_sec: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    resolution: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    container: Optional[str] = None


def _ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def probe_media(path: Path) -> ProbeResult:
    """用 ffprobe 探测媒体文件；任何失败都返回空 ProbeResult，不抛异常"""
    if not _ffprobe_available():
        return ProbeResult()
    try:
        proc = subprocess.run(
            [*_FFPROBE, str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            logger.debug(f"ffprobe rc={proc.returncode} for {path.name}")
            return ProbeResult()
        data = json.loads(proc.stdout)
    except Exception as e:  # noqa: BLE001 - 探测是增强，任何异常都降级
        logger.debug(f"ffprobe error for {path.name}: {e}")
        return ProbeResult()

    res = ProbeResult()
    # 时长（format.duration 或 stream）
    fmt = data.get("format") or {}
    duration = fmt.get("duration")
    if duration:
        try:
            res.duration_sec = int(float(duration))
        except (ValueError, TypeError):
            pass
    # 容器
    container = (fmt.get("format_name") or "").split(",")[0]
    res.container = container or None

    # 视频/音频流
    streams = data.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if video_stream:
        res.video_codec = video_stream.get("codec_name")
        try:
            res.width = int(video_stream.get("width") or 0)
            res.height = int(video_stream.get("height") or 0)
        except (ValueError, TypeError):
            pass
        if res.height:
            # 优先用探测到的真实高度
            h = min(res.height, res.width) if res.height > res.width else res.height
            res.resolution = _HEIGHT_TO_RES.get(h)
        # 若无高度映射，fallback 用命名解析结果（由调用方回填）
    if audio_stream:
        res.audio_codec = audio_stream.get("codec_name")

    return res


# ---------------------------------------------------------------------------
# 入库
# ---------------------------------------------------------------------------

# 名称可识别字符过多时做粗粒度来源过滤——仅统计用，不做复杂分类
_VIDEO_NAME_RE = re.compile(r"\.(mp4|mkv|avi|mov|m4v|ts|webm)$", re.IGNORECASE)


def _iter_media_files(root: Path):
    """递归遍历目录，yield 视频文件（跳过 <10MB 的碎片）"""
    if not root.exists() or not root.is_dir():
        return
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in VIDEO_EXTS:
            continue
        try:
            if p.stat().st_size < _MIN_SIZE:
                logger.debug(f"skip small file: {p.name} ({p.stat().st_size}B)")
                continue
        except OSError:
            continue
        yield p


def upsert_movie(db: Session, path: Path) -> tuple[Movie, bool]:
    """按 file_path 幂等插入/更新。

    返回 (movie, created)。新增则全字段写入；已存在只补空字段，
    不覆盖用户可能改动的 title 等。
    """
    path_s = str(path)
    parsed = parse_filename(path)
    probe = probe_media(path)
    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = None

    existing = db.query(Movie).filter(Movie.file_path == path_s).first()

    if existing:
        # 已存在：只补空字段（探测信息可能比导入时更全）
        if not existing.title and parsed.title:
            existing.title = parsed.title
        if existing.duration_sec is None and probe.duration_sec:
            existing.duration_sec = probe.duration_sec
        if existing.file_size is None and file_size:
            existing.file_size = file_size
        if not existing.container and probe.container:
            existing.container = probe.container
        db.commit()
        return existing, False

    # 新增
    if not parsed.title:
        parsed.title = path.stem
    movie = Movie(
        file_path=path_s,
        title=parsed.title,
        title_en=parsed.title_en,
        year=parsed.year,
        resolution=probe.resolution or parsed.resolution,
        source=parsed.source,
        video_codec=probe.video_codec,
        audio_codec=probe.audio_codec,
        container=probe.container or (path.suffix.lstrip(".").lower()),
        duration_sec=probe.duration_sec,
        file_size=file_size,
        has_subtitle=False,
        status="active",
    )
    db.add(movie)
    try:
        db.commit()
        db.refresh(movie)
        return movie, True
    except IntegrityError:
        # file_path 并发冲突 → 回滚，视为已存在
        db.rollback()
        existing = db.query(Movie).filter(Movie.file_path == path_s).first()
        return existing, False


@dataclass
class ScanResult:
    """扫描结果统计"""
    added: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    scanned: int = 0
    dir: str = ""


def scan_movies(db: Session, root: Path | None = None) -> ScanResult:
    """扫描媒体目录并幂等入库。

    Args:
        db: SQLAlchemy Session
        root: 要扫描的目录；None 则用 settings.movies_dir
    """
    settings = get_settings()
    scan_root = root or settings.movies_dir
    result = ScanResult(dir=str(scan_root))

    if not scan_root.exists() or not scan_root.is_dir():
        result.failed += 1
        result.errors.append(f"movies_dir does not exist: {scan_root}")
        logger.error(f"scan aborted: {scan_root} not a dir")
        return result

    files = list(_iter_media_files(scan_root))
    result.scanned = len(files)
    logger.info(f"scan: found {len(files)} media files under {scan_root}")

    for p in files:
        try:
            _, created = upsert_movie(db, p)
            if created:
                result.added += 1
            else:
                result.skipped += 1
        except Exception as e:  # noqa: BLE001 - 单文件失败不中断整批
            db.rollback()
            result.failed += 1
            result.errors.append(f"{p.name}: {e}")
            logger.error(f"scan failed on {p.name}: {e}")

    logger.info(
        f"scan done: dir={scan_root} scanned={result.scanned} "
        f"added={result.added} skipped={result.skipped} failed={result.failed}"
    )
    return result
