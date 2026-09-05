# 家庭影院 · 代码同步说明

> 本文档说明：如何把 `if-pi05` 上的 `kb_manager` 项目代码同步到本机 Claw 仓库、如何在本地继续开发、如何与远端保持一致。

---

## 1. 目录布局

```
Claw/eldcare-kb-manager/
├── README.md                  # 项目入口
├── REQUIREMENTS.md            # 需求分析
├── DESIGN.md                  # 技术方案
├── SYNC.md                    # 本文档（同步说明）
├── pi05-legacy/               # 从 if-pi05 拉过来的 Flask 旧版代码（参考基线）
│   ├── app.py                 # Flask 主程序（13.5KB）
│   ├── database.py            # 数据访问层（12.7KB）
│   ├── crawler.py             # 通用爬虫
│   ├── auto_download.py       # 自动下载调度
│   ├── bilibili_crawler.py
│   ├── download_movie.py
│   ├── download_subtitles.py
│   ├── mt_http_server.py      # aiohttp 多线程 Range 服务
│   ├── multi_download.py
│   ├── relay_download.py      # libtorrent 中继下载
│   ├── relay_lt.py
│   ├── security.py
│   ├── wget_download.sh
│   ├── start.sh               # 启动脚本
│   ├── requirements.txt       # Flask / aiohttp / libtorrent / ...
│   ├── static/
│   │   ├── app.js
│   │   └── style.css
│   ├── templates/
│   │   ├── index.html         # 19.8KB
│   │   ├── player.html        # 11.6KB
│   │   └── http_range_server.py
│   └── db-schema/
│       ├── schema.sql         # 5 张表的 CREATE TABLE
│       ├── stats.json         # 行数 / 列结构 / 索引
│       ├── movies.db          # 数据库副本（118KB）
│       └── samples/           # 前 3 行样例数据
└── v2/                        # 即将开发的新版（FastAPI）
```

---

## 2. 已同步的 if-pi05 数据库结构

| 表 | 行数 | 字段 | 说明 |
|----|------|------|------|
| `movies` | 55 | 30 字段 | 影片主表（含 TMDB 字段） |
| `categories` | 13 | 6 字段 | 自动分类 + 手工分类 |
| `search_history` | 74 | 3 字段 | 搜索记录 |
| `watch_history` | 39 | 4 字段 | 播放进度 |
| `sqlite_sequence` | 4 | 2 字段 | SQLite 自动维护 |

**字段命名特点**：
- `title`（中文）+ `title_en`（英文）双标题
- `poster` / `cover_url` 双海报字段（poster=本地缩略图、cover=TMDB 原图）
- `video_url` / `subtitle_url` / `magnet`（待下载种子）
- `is_favorite` / `is_bookmark` 布尔收藏
- `duration` 单位：秒
- `status`：可能值（active / deleted / pending）

完整 schema 见 `pi05-legacy/db-schema/schema.sql`，样例数据见 `pi05-legacy/db-schema/samples/`。

---

## 3. 同步脚本（已固化到 `.workbuddy/tmp/`）

```bash
# 同步代码 + 排除大文件/缓存
python .workbuddy/tmp/sync_kb_manager.py

# 同步 DB schema + 样例 + 副本
python .workbuddy/tmp/dump_db_schema.py
```

输出统计：

```
=== done: 23 files copied ===
+ app.py (13513B)
+ database.py (12780B)
+ crawler.py (23162B)
... 等
- skip dir: __pycache__ / venv / static/thumbs / subtitles
- skip file: *.log / nohup.out / movies.db.bak_* / *.pyc
```

排除规则可在脚本顶部 `SKIP_DIRS` / `SKIP_FILES` 调整。

---

## 4. 本地一键启动旧版（验证用）

```bash
cd pi05-legacy
python -m venv venv
./venv/bin/pip install -r requirements.txt
./start.sh         # 默认端口 5001
# 浏览器打开 http://127.0.0.1:5001
```

> 注意：旧版 movies 软链指向 `/mnt/ztv/movies`（if-pi05 上的 1.8T 硬盘），本机没这块硬盘，需要在 `app.py` 里把 `MoviesFolder` 改成本地媒体目录，或软链到本机某个放电影的目录。

---

## 5. 与 if-pi05 的协作约定

| 场景 | 约定 |
|------|------|
| 本地改 `pi05-legacy/` | 改完同步回 pi05，**只**用于验证 / 学习；正式开发在 `v2/` |
| V2 上线后 | 把 `pi05-legacy/` 标记为 archive（不再维护） |
| 数据库 schema 变更 | 改完后立即重新跑 `dump_db_schema.py` 更新 `db-schema/` |
| 数据库主从 | V2 设计采用主（pi05）+ 辅（本机）双节点，详见 DESIGN.md §6 |

---

## 6. 在 VS Code 中打开

```bash
code C:\Users\zhangwenan\WorkBuddy\Claw\eldcare-kb-manager
```

CodeBuddy IDE 插件会自动识别项目结构、提供 AI 补全 / `/tests` / `/review` 等。

---

## 7. 待办（V2 启动前）

1. 建立 `v2/` 目录，初始化 FastAPI + SQLAlchemy 骨架
2. 把旧版 `app.py` 的路由逐一映射到新版 `/api/v2/...`
3. 写 `services/scanner.py` 替换旧版 `database.py` 的解析逻辑
4. PWA manifest + service-worker 配置
5. 主备同步协议实现
6. 修 if-pi05 的 nms-agent（9100）和 mcp_edge_server（8123），让本地能监控

详见 `DESIGN.md` §7 演进路径。
