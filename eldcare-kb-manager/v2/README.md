# ELDCARE KB Manager V2

家庭影院 V2 — FastAPI + SQLAlchemy + aria2c RPC 主控节点

## 快速开始

```bash
# Linux / macOS（含 pi05 节点）
cd v2
python -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
./.venv/bin/python -m app.main
# 或：
./.venv/bin/uvicorn app.main:app --reload
```

```powershell
# Windows（PowerShell）
cd v2
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m app.main
# 或：
.\.venv\Scripts\uvicorn app.main:app --reload
```

浏览器打开 <http://127.0.0.1:8090>。

> 监听地址由 `.env` 的 `ELDCARE_HOST` / `ELDCARE_PORT` 控制（`python -m app.main` 会读取），
> 默认 `0.0.0.0:8090`；直接用 uvicorn 命令时可用 `--host/--port` 临时覆盖。

## 模块

| 模块 | 作用 |
|------|------|
| `app/main.py` | FastAPI 入口 + 路由聚合 |
| `app/core/config.py` | 配置（Pydantic Settings） |
| `app/core/db.py` | SQLAlchemy + SQLite WAL |
| `app/core/logging.py` | 日志统一格式 |
| `app/models/` | ORM 模型 |
| `app/api/` | 路由模块 |
| `app/services/` | 业务服务（scanner / metadata / thumb / transcoder / sync）— 规划中，尚未创建 |
| `app/static/` | 前端单页应用 + PWA |
| `scripts/` | 运维脚本（规划中） |
| `tests/` | 单元测试（规划中，目录暂缺） |

## 配置（.env）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ELDCARE_PORT` | 8090 | 服务端口 |
| `ELDCARE_NODE_ROLE` | master | master / slave |
| `ELDCARE_DATA_DIR` | ./data | 数据目录 |
| `ELDCARE_MOVIES_DIR` | ${ELDCARE_DATA_DIR}/movies | 媒体目录 |
| `ELDCARE_PEER_URL` | (空) | 主备对端 URL |
| `ELDCARE_PEER_TOKEN` | (空) | 主备鉴权 token |
| `ELDCARE_TMDB_API_KEY` | (空) | TMDB 密钥 |
| `ELDCARE_ARIA2_RPC_URL` | http://127.0.0.1:6800/jsonrpc | aria2 RPC |
| `ELDCARE_ARIA2_SECRET` | (空) | aria2 RPC token |

## API

完整文档：启动后访问 `/docs`（FastAPI 自动生成）。

### V2 已实现

- `GET  /api/v2/health` — 健康检查
- `GET  /api/v2/version` — 版本与实例信息
- `GET  /api/v2/library/movies` — 影片列表（分页/分类/搜索）
- `GET  /api/v2/library/movies/{id}` — 影片详情
- `GET  /api/v2/library/categories` — 分类列表
- `GET  /api/v2/library/stats` — 库统计
- `GET  /api/v2/player/stream/{id}` — Range 流播放
- `GET  /api/v2/player/subtitle/{id}.vtt` — 字幕（待实现）
- `WS   /api/v2/ws/events` — 实时事件（待实现）

## 与 if-pi05 同步

详见 [/SYNC.md](../SYNC.md)。本目录（v2/）在本地开发，
`pi05-legacy/` 保留旧版 Flask 代码作为参考基线。
