# CodeBuddy 任务单：修复 movie 默认值 + 实现 scanner

> 项目根：`eldcare-kb-manager/v2`（当前 VS Code 已打开）
> 配套规格：`../DESIGN.md` §4 模块设计、§7.1 文件名解析
> 数据环境：if-pi05 上 `/mnt/ztv/movies`（34 个媒体文件，32 已入库），ffprobe 7.1.5 可用

请按下面两块任务完成改动。**改完不要推 GitHub**，完成后告诉我（老张/WorkBuddy 侧负责部署到 if-pi05 并 push）。改动全程用 SQLAlchemy ORM 做写操作，禁止裸 sqlite3 INSERT（除非同步加 server_default）。

---

## 任务 1：修 `app/models/movie.py` 的 NOT NULL 无 DB 默认列

**背景**：以下列在 ORM 层有 Python `default=`，但建表时 SQLAlchemy **不会**把默认写进 SQLite DDL，导致这几列在 DB 里是 `NOT NULL` 且无默认。若用裸 sqlite3 INSERT 且未显式给值会报 `NOT NULL constraint failed`。

**改动**：给这些列追加 `server_default=text("...")`，使 DB 层也有默认值（未来建表/迁移受益）。需要从 `sqlalchemy` 引入 `text`：

| 列 | 现值 | 建议 server_default |
|---|---|---|
| `has_subtitle` | `Boolean, default=False` | `server_default=text("0")` |
| `download_status` | `String(32), default="none"` | `server_default=text("'none'")` |
| `status` | `String(16), default="active", index=True` | `server_default=text("'active'")` |
| `view_count` | `Integer, default=0` | `server_default=text("0")` |
| `like_count` | `Integer, default=0` | `server_default=text("0")` |
| `is_favorite` | `Boolean, default=False, index=True` | `server_default=text("0")` |

保留原有 Python `default=`（ORM 语义不变），两者并存。

> 注：`server_default` 只影响**新建表**。存量库（pi05 已建表）不会自动重写 DDL，无需为此做破坏性迁移——scanner 走 ORM 插入时 Python default 已能兜底。DB 级默认是为未来表重建/从零部署准备的健壮性增强。

---

## 任务 2：实现 `app/services/scanner.py`

目录 `app/services/` 尚不存在，请一并创建（含 `app/services/__init__.py`）。目标：扫描媒体目录、解析元数据、探测文件、**幂等入库**。

### 2.1 扫描入口 & 返回
```python
async def scan_movies(db: Session) -> ScanResult:
    """扫描 settings.movies_dir，幂等入库，返回新增/跳过/失败统计"""
```
建议 `ScanResult` 用 dataclass：`added:int, skipped:int, failed:int, errors:list[str]`。用同步 SQLAlchemy `Session` 即可（不强制 async，保持与现有 library/player 一致——它们都是 `Session = Depends(get_db)` 同步风格）。

### 2.2 文件发现
- 递归遍历 `settings.movies_dir`（来自 `app.core.config.get_settings()`）
- 只收视频扩展：`.mp4 .mkv .avi .mov .ts .m4v .webm`（与 `app/api/player.py` 的 mime 表对齐）
- 跳过已入库文件：用 `SELECT file_path FROM movies WHERE status != 'deleted'` 建集合对比，`file_path` 已入库则 skip（幂等）
- 跳过非视频、隐藏文件、小于 10MB 的碎片（可选）

### 2.3 文件名解析（DESIGN §7.1 正则，按优先级匹配）
```python
_PATTERNS = [
    # 1. 名称.年份.来源.分辨率
    re.compile(r"^(?P<title>.+?)\s*[\.\s](?P<year>\d{4})[\.\s](?P<source>WEB-?DL|BluRay|HDTV|REMUX|HD).*?\.(?P<res>\d+p|UHD)", re.I),
    # 2. 名称.年份.分辨率
    re.compile(r"^(?P<title>.+?)\s*[\.\s](?P<year>\d{4})[\.\s].*\.(?P<res>\d+p|UHD)", re.I),
    # 3. 名称 (年份).分辨率
    re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*[\.\s].*\.(?P<res>\d+p|UHD)", re.I),
]
def parse_filename(path: Path) -> ParsedMeta:
    """返回 title/title_en/year/resolution/source；fallback：去后缀作 title"""
```
- 标题里 `.` 和 `_` 统一替换为空格；中英文混排时中文部分进 `title`，若解析出的首段是英文则同时填 `title_en`（简单启发即可，不苛求）。
- `resolution` 归一化：`1080p`→`1080p`、`2160p`/`UHD`→`4K`。
- `source` 归一化大写：`web-dl`→`WEB-DL` 等。

### 2.4 ffprobe 探测（可选增强，捕获失败不中断）
每文件用 `subprocess` 调 `ffprobe`（JSON 输出）取：`duration_sec`（format.duration 取整）、`width/height`（第一个 video stream → 映射 resolution）、`video_codec`（codec_name）、`audio_codec`（首个 audio stream）。任一字段探测失败置 None，不抛异常。
```python
FFPROBE = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams"]
```
如果 ffprobe 不在 PATH 或执行异常，全部走「无探测」路径（只填 file_path/title/size），保证扫描永不因探测崩溃。

### 2.5 入库（关键：走 ORM + file_path 幂等）
```python
def upsert_movie(db: Session, path: Path) -> Movie:
    m = db.query(Movie).filter(Movie.file_path == str(path)).first()
    if not m:
        m = Movie(file_path=str(path))       # 其余交给模型 default
        db.add(m)
    # 补元数据（新增填全，已存在只补空字段，不覆盖用户可能改的 title 等）
    m.title = m.title or parsed.title
    ...
    db.commit(); db.refresh(m); return m
```
- **用 ORM `Movie(...)` 构造**（Python default 生效），不要裸 INSERT。
- `file_size = path.stat().st_size`（int）。
- `category` 暂不强制（可留空，前端按需）。
- 每文件独立 commit，避免单文件失败污染整批；捕获 `IntegrityError` → rollback 计数到 `skipped/failed`。

### 2.6 日志
用 `app.core.logging.logger`（loguru），扫描完成打一行摘要：`scan done: added=.. skipped=.. failed=..`

---

## 任务 3：接线（入口）

在 `app/main.py`：
1. 顶部 import `from app.services.scanner import scan_movies`（若放 lifespan 需用 sync Session + 在 `db.py` 拿 session；建议**不在启动时自动全扫**——避免每次重启全量 ffprobe 慢。改为暴露手动触发更可控）
2. 新增一个扫描触发接口（建议放 `app/api/admin.py`，router prefix `/api/v2/admin`）：
   - `POST /api/v2/admin/scan` → 开线程或直接同步执行 `scan_movies`，返回 `ScanResult`
   - 若为异步事件循环，用 `run_in_executor` 或直接同步函数均可（本项目路由多为同步）
3. 在 `app/main.py` 的 `include_router` 处挂上 admin router。

> 是否在 lifespan 启动时自动扫描一次，你权衡后决定并写清楚理由。考虑到首次部署要能把 34 个文件全扫进去，我建议提供 `POST /api/v2/admin/scan` 手动触发，调用一次即可（也可在 lifespan 末尾异步触发一次初始扫描，二者选一）。

---

## 验收标准（改完本地自测再交付）
1. `python -m uvicorn app.main:app --port 809X` 能起，`/api/v2/health` 200。
2. `POST /api/v2/admin/scan` 返回结构含 `added/skipped/failed`，且不会抛 500。
3. 对本机一个含测试文件的目录扫描能正确解析 `长安三万里.2023.WEB-DL.1080p.mkv` → title/year/resolution/source 正确（可在 venv 里写个临时脚本单测 `parse_filename`，不强制留测试文件）。
4. movie 模型改动后，`from app.models.movie import Movie` + `Movie(status=...)` 语义不变，原查询不受影响。

完成后告诉我「scanner + movie 默认值已改完」，由我来做 pi05 部署验证（会真实扫描 /mnt/ztv/movies 的 34 个文件）并 push GitHub。
