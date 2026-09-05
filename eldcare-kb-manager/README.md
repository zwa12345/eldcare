# 家庭影院 (eldcare-kb-manager)

老张家家庭影院项目 — 含需求、技术方案、if-pi05 旧版代码基线与本地开发指南。

## 文档入口

| 文档 | 内容 |
|------|------|
| [REQUIREMENTS.md](./REQUIREMENTS.md) | 需求分析（用户、功能、非功能、验收） |
| [DESIGN.md](./DESIGN.md) | 技术方案（架构图、模块、API、数据模型、演进） |
| [SYNC.md](./SYNC.md) | 与 if-pi05 代码同步说明 |
| [pi05-legacy/](./pi05-legacy/) | if-pi05 上的旧版 Flask 代码（参考基线） |

## 现状速览

- **运行节点**：if-pi05 (Debian 13, Pi 5 8G, 1.8T 外置硬盘)
- **端口**：5001（Flask，旧版）
- **数据库**：SQLite（118KB，55 部电影 + 13 分类 + 74 搜索 + 39 进度）
- **媒体源**：`/mnt/ztv/movies`（30+ 部已扫描入库）
- **自动下载**：每 30 分钟从 YTS 抓热门 → 中继 libtorrent → HTTP 回传

## V2 目标

把单 Flask + SQLite 升级为：

- FastAPI + SQLAlchemy + aria2 RPC 主控
- if-pi05 主节点 + 本机辅节点（双 SQLite 同步）
- PWA 移动端 / 远程遥控 / 多用户
- AI 增强（whisper.cpp 字幕生成、推荐）
- 一体化前端（深色影院主题 + vidstack 播放器）

详见 [DESIGN.md](./DESIGN.md)。

## 快速开始

```bash
# 1. 在 VS Code 中打开
code .

# 2. 跑旧版（仅用于本地验证 pi05 上的代码）
cd pi05-legacy && ./start.sh    # 默认 5001

# 3. V2 开发（待启动）
cd v2 && uvicorn app.main:app --reload --port 8090
```

## 相关项目

- `~/HomeTheater/`（Windows 本机）— V1 简化版（FastAPI + 内存数据库）
- `if-pi05:/home/pi/.hermes/` — Hermes AI Agent 框架（驱动自动下载）

## 维护者

- 老张（zwa12345）
- WorkBuddy agent（自动化同步 / 报告）
