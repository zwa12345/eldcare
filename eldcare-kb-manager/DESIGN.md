# 家庭影院 · 技术方案（V2.0）

> 配套文档：`REQUIREMENTS.md`
> 整理时间：2026-09-05
> 替代方案：单 Flask + SQLite（kb_manager 现状）→ **主备双节点 + 共享元数据库**

---

## 1. 架构总览

```
┌────────────────────────────────────────────────────────────────┐
│                       家庭局域网 / Tailscale VPN                │
│                                                                │
│  ┌──────────────────────┐         ┌─────────────────────────┐ │
│  │   if-pi05 (Pi 5)     │         │  老张本机 (Windows)      │ │
│  │   "主控 + 媒体柜"    │         │   "前台 + AI 增强"      │ │
│  │                      │         │                         │ │
│  │  ┌────────────────┐  │         │  ┌────────────────────┐ │ │
│  │  │ kb_manager v2  │◄─┼────HTTP─┼─►│ HomeTheater v2     │ │ │
│  │  │ (FastAPI)      │  │  同步    │  │ (FastAPI)          │ │ │
│  │  │ port 8090      │  │         │  │ port 8091          │ │ │
│  │  └───────┬────────┘  │         │  └─────────┬──────────┘ │ │
│  │          │           │         │            │            │ │
│  │   ┌──────▼──────┐    │         │   ┌────────▼────────┐   │ │
│  │   │ SQLite      │    │         │   │ SQLite (镜像)    │   │ │
│  │   │ movies.db   │    │         │   │ movies.db (RO 缓存)│  │ │
│  │   │ (主库)      │    │         │   └────────┬────────┘   │ │
│  │   └──────┬──────┘    │         │            │            │ │
│  │          │           │         │            ▼            │ │
│  │   ┌──────▼──────┐    │         │   ┌────────────────────┐ │ │
│  │   │ /mnt/ztv    │    │         │   │ CodeBuddy 增强     │ │ │
│  │   │ 1.8TB exfat │    │         │   │  - 字幕生成 whisper│ │ │
│  │   │  电影库     │    │         │   │  - 视频摘要 AI     │ │ │
│  │   └──────┬──────┘    │         │   │  - 异机下载接力   │ │ │
│  │          │           │         │   └────────────────────┘ │ │
│  │   ┌──────▼──────┐    │         │                         │ │
│  │   │  aria2c     │    │         │   ┌────────────────────┐ │ │
│  │   │  BT 引擎    │    │         │   │ WorkBuddy 调度     │ │ │
│  │   └─────────────┘    │         │   │ （你正在看我）     │ │ │
│  └──────────────────────┘         │   └────────────────────┘ │ │
│                                   └─────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
                        ▲                       ▲
                        │                       │
                  ┌─────┴─────┐         ┌───────┴────┐
                  │  电视盒    │         │  手机/平板  │
                  │  PWA 客户端│         │  PWA 客户端 │
                  └───────────┘         └────────────┘
```

---

## 2. 分工定位

| 维度 | if-pi05（Pi 5） | 老张本机（Windows） |
|------|------------------|----------------------|
| **角色** | 主控节点（永远在线） | 前台节点（临时在线） |
| **媒体存储** | ✅ `/mnt/ztv` 1.8TB | — |
| **下载引擎** | ✅ aria2c BT | — |
| **DB 主库** | ✅ SQLite 写权限 | 只读镜像 + 定时 pull |
| **AI 增强** | 弱（CPU 推理慢） | ✅ whisper / 摘要 / 异源接力 |
| **Web 服务** | ✅ FastAPI（端口 8090） | ✅ FastAPI（端口 8091，可选启停） |
| **浏览器客户端** | ✅ 内嵌服务（always on） | ✅ 通过 Tailscale 域名访问 pi05 |
| **电源** | 24×7 低功耗（~10W） | 按需开关 |

---

## 3. 技术选型

### 3.1 后端

| 项 | 选择 | 理由 |
|------|------|------|
| Web 框架 | **FastAPI** | 异步、原生 OpenAPI、性能优于 Flask；现有 HomeTheater 已验证 |
| 数据库 | **SQLite 3** + WAL 模式 | 单机够用；支持 backup API；零运维 |
| ORM | **SQLAlchemy 2.x** | 主流、迁移工具完善 |
| 任务队列 | **APScheduler + asyncio** | 内嵌、轻量；不要 Celery |
| 下载引擎 | **aria2c JSON-RPC** | 磁力/种子/HTTP 多协议、断点续传、限速 |
| 视频处理 | **ffmpeg** | 转封装、转码、抽帧 |
| 元数据 | **TMDB API**（需 key）+ 本地缓存 | 行业标准、中文支持好 |
| 字幕 | **whisper.cpp**（本机）/ OpenSubtitles（在线） | 本机 AI 字幕 + 在线备用 |
| 鉴权 | **JWT**（一次性 token + 设备指纹） | 家庭场景不需要完整 OAuth |

### 3.2 前端

| 项 | 选择 | 理由 |
|------|------|------|
| 框架 | **原生 ES Modules + Alpine.js** | 单页应用够用，不引入构建链 |
| 样式 | **CSS 变量 + Grid + 自研深色影院主题** | 不引入 Tailwind/Bootstrap |
| 播放器 | **vidstack**（基于 hls.js + 原生 `<video>`） | M3U8 + MP4 + Range 全支持 |
| PWA | **manifest + service-worker** | 移动端添加到主屏 |
| 图标 | **lucide-icons**（SVG 内联） | 风格统一、轻量 |
| 多端适配 | **CSS Grid 自适应 + rem 字体** | 手机/平板/电视均可用 |

### 3.3 部署 & 运维

| 项 | 选择 |
|------|------|
| 进程守护 | if-pi05: `systemd user service`；本机: Windows Service / 守护脚本 |
| 反向代理 | 不引入 nginx；FastAPI 直跑足够 |
| HTTPS | 自签证书 + LAN 内忽略证书警告；Tailscale 已加密 |
| 监控 | if-pi05: 修好 nms-agent（9100）；本机: 简易心跳脚本 |
| 备份 | DB 每日 cron 备份至 `/mnt/ztv/backups/`；保留 7 天 |
| 日志 | 滚动日志，按天切割，保留 30 天 |

---

## 4. 模块设计

```
eldcare-kb-manager/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口 + 路由聚合
│   ├── config.py               # 路径/端口/密钥配置
│   ├── db.py                   # SQLAlchemy + SQLite WAL
│   ├── models/
│   │   ├── movie.py            # 影片主表
│   │   ├── category.py         # 分类
│   │   ├── tag.py              # 标签
│   │   ├── user.py             # 用户（含 device_fingerprint）
│   │   ├── watch_position.py   # 播放进度
│   │   └── download_task.py    # 下载任务
│   ├── api/
│   │   ├── library.py          # 浏览/搜索/分类
│   │   ├── player.py           # 流播放/Range/字幕
│   │   ├── download.py         # aria2 RPC 包装
│   │   ├── source.py           # 公版片源爬虫
│   │   ├── admin.py            # 扫描/入库/分类
│   │   └── user.py             # 登录/进度/收藏
│   ├── services/
│   │   ├── scanner.py          # 文件扫描 + 文件名解析
│   │   ├── metadata.py         # TMDB API + 缓存
│   │   ├── thumb.py            # ffmpeg 抽帧
│   │   ├── transcoder.py       # MKV→MP4 装换
│   │   ├── subtitle.py         # 字幕下载/AI 生成
│   │   └── sync.py             # 主备同步（HTTP pull/push）
│   ├── static/
│   │   ├── index.html          # 单页应用
│   │   ├── manifest.webmanifest  # PWA 配置
│   │   ├── sw.js               # Service Worker
│   │   ├── css/
│   │   ├── js/
│   │   └── icons/
│   └── templates/              # （如需服务端渲染时使用）
├── tests/
├── scripts/
│   ├── install.sh              # 一键安装
│   ├── start.sh                # 启动
│   ├── backup.sh               # DB 备份
│   └── sync.sh                 # 主备同步
├── systemd/
│   └── kb-manager.service      # 用户级 service 模板
├── data/                       # 本地数据目录（gitignored）
│   ├── movies.db
│   ├── thumbs/
│   ├── subtitles/
│   └── downloads/
├── requirements.txt
├── pyproject.toml
├── README.md
└── CHANGELOG.md
```

---

## 5. 数据模型（核心表）

```sql
-- 影片主表
CREATE TABLE movies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path   TEXT UNIQUE NOT NULL,      -- 绝对路径
    title       TEXT NOT NULL,
    year        INTEGER,
    resolution  TEXT,                       -- 4K / 1080p / 720p
    source      TEXT,                       -- WEB-DL / BluRay / WEB
    tmdb_id     INTEGER,
    poster_url  TEXT,
    backdrop_url TEXT,
    overview    TEXT,
    rating      REAL,
    duration_sec INTEGER,
    category    TEXT,                       -- 自动分类
    tags        TEXT,                       -- JSON array
    file_size   INTEGER,
    video_codec TEXT,                       -- h264 / h265 / av1
    audio_codec TEXT,
    has_subtitle INTEGER DEFAULT 0,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_movies_category ON movies(category);
CREATE INDEX idx_movies_added_at ON movies(added_at DESC);
CREATE INDEX idx_movies_title ON movies(title);

-- 分类
CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    slug TEXT UNIQUE,
    sort_order INTEGER DEFAULT 0,
    auto BOOLEAN DEFAULT 1                  -- 自动生成 vs 手工
);

-- 收藏 / 标签（多对多）
CREATE TABLE user_favorites (
    user_id INTEGER,
    movie_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, movie_id)
);

-- 播放进度
CREATE TABLE watch_positions (
    user_id INTEGER,
    movie_id INTEGER,
    position_sec INTEGER NOT NULL,
    duration_sec INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, movie_id)
);

-- 演员 / 类型（TMDB 拉取后存）
CREATE TABLE credits (
    movie_id INTEGER,
    person_id INTEGER,
    name TEXT,
    role TEXT,                              -- actor / director / writer
    PRIMARY KEY (movie_id, person_id, role)
);

-- 下载任务
CREATE TABLE download_tasks (
    gid TEXT PRIMARY KEY,                   -- aria2 gid
    uri TEXT NOT NULL,
    save_path TEXT,
    filename TEXT,
    total_bytes INTEGER,
    done_bytes INTEGER DEFAULT 0,
    status TEXT,                            -- queued / active / paused / done / error
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 系统配置 KV
CREATE TABLE kv_store (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. API 设计（V2 替代 V1）

| V1（Flask） | V2（FastAPI） | 改进 |
|-------------|---------------|------|
| `/api/movies` | `/api/v2/library/movies?page=&size=&cat=&q=` | 分页 + 参数化 |
| `/api/video/<id>/stream` | `/api/v2/player/stream/<id>` + `Range` 支持 + `Accept-Ranges: bytes` | Range 头 |
| `/api/crawl/douban` | `/api/v2/source/search?q=&provider=archive/yts/bilibili` | 多源统一 |
| `/api/movies/stats` | `/api/v2/library/stats` + WebSocket 增量推送 | 实时 |
| 无 | `/api/v2/sync/pull?since=` + `/api/v2/sync/push` | 主备同步 |
| 无 | `/api/v2/player/subtitle/<id>.vtt` | 自动生成 VTT |
| 无 | `WS /api/v2/ws/events` | 下载进度推送 |

完整 OpenAPI 文档自动生成于 `/docs`（FastAPI 原生）。

---

## 7. 关键算法

### 7.1 文件名解析（`scanner.py`）

```
输入：/mnt/ztv/movies/长安三万里.2023.WEB-DL.1080p.mkv
输出：
  title: 长安三万里
  year: 2023
  resolution: 1080p
  source: WEB-DL
```

正则模板（按优先级）：
1. `^(?P<title>.+?)\s*[\.\s](?P<year>\d{4})[\.\s](?P<source>WEB-?DL|BluRay|HDTV|REMUX|HD).*?\.(?P<res>\d+p|UHD)`
2. `^(?P<title>.+?)\s*[\.\s](?P<year>\d{4})[\.\s].*\.(?P<res>\d+p|UHD)`
3. `^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*[\.\s].*\.(?P<res>\d+p|UHD)`
4. fallback: 文件名去后缀即为标题

### 7.2 缩略图生成（`thumb.py`）

```
1. ffprobe 取时长
2. 取 10% 处 / 50% 处 / 90% 处三帧 → 选最锐利一张（基于 Laplacian 方差）
3. 缩放至 600x900，长边填充黑边
4. 存为 data/thumbs/<id>.jpg，质量 80
5. 同时存 backdrop（1920x1080 横版）
```

### 7.3 主备同步（`sync.py`）

```
每 30 分钟一次：
  本机 → if-pi05: GET /api/v2/sync/changes?since=<last_sync_at>
  服务端返回：增量 movies + categories + watch_positions
  本机 SQLite 写入（覆盖式）
  本机 → if-pi05: POST /api/v2/sync/watch_positions（本机独有的进度）

冲突策略：last-write-wins，按 updated_at
媒体文件：始终以 pi05 为准，本机不存
```

---

## 8. 安全设计

| 风险 | 防护 |
|------|------|
| TMDB API key 泄漏 | 用 `.env` + `.gitignore`，不进仓库 |
| 局域网扫描 | 服务 bind 0.0.0.0，但加 IP 白名单（家庭设备 Tailscale 网段）|
| 上传恶意文件 | Web 不提供上传入口；只有 aria2 下载 |
| SQL 注入 | SQLAlchemy ORM 参数化 |
| XSS | 前端不写 innerHTML，统一用 textContent / DOMPurify |
| CSRF | 纯 API + JWT，无 cookie 场景 |
| 暴力播放 | 单设备 token + 简单 rate limit |

---

## 9. 演进路径

### V1（现在，已存在）

> kb_manager Flask + SQLite（pi05）+ HomeTheater FastAPI（本机）

合并现状 → 一个统一仓库。

### V2（MVP，2 周内）

- 代码重构为 FastAPI 主 + 前端单页
- 主备双节点（pi05 主、本机辅）
- 完整下载链路（aria2 + TMDB）
- PWA 基础体验

### V3（1 个月内）

- 本机 AI 字幕生成（whisper.cpp）
- 多用户 / 儿童模式
- 远程遥控 + DLNA 投屏

### V4（长线）

- 推荐系统
- 自动追新
- 跟企业微信打通（观影报告 / 新片推荐）

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 老张本机不开时，AI 字幕/异源接力不可用 | 字幕可由 pi05 调远程 API 或离线缓存；推荐异步排队 |
| TMDB 限流（40 req/s） | 本机缓存元数据 + 限速器 |
| `/mnt/ztv` exfat 不支持符号链接/权限 | 已用软链做反向兼容；权限用 uid 1000 |
| 数据同步冲突 | last-write-wins + 定期快照 |
| 移动端浏览器兼容 | 现代浏览器（PWA 不支持 IE） |

---

## 11. 一句话总结

> 把"if-pi05 跑媒体柜 + 下载引擎、本机跑 AI 增强 + 前台、SQLite 双向同步"的分布式家庭影院做出来，2 周出 MVP，1 个月打磨完整体验；老张家所有设备都能看片、找片、自动下载。
