# eldcare-kb-manager V2 — if-pi05 部署记录

> 更新日期：2026-09-06
> 部署目标：if-pi05（Tailscale 100.64.0.21，Debian 13 trixie / aarch64 / Pi5）
> 应用：家庭影院 V2（FastAPI + SQLAlchemy + PWA），主控节点 master

## 部署结果概览

| 项 | 值 |
|---|---|
| 代码位置 | `/home/pi/eldcare/eldcare-kb-manager/v2` |
| 服务名 | `eldcare-v2.service`（systemd 用户服务，已 enable 开机自启） |
| 监听端口 | **8090**（V1 家庭影院仍占用 5001，两者并存互不影响） |
| Python | 系统 python3（3.13.5），独立 `.venv` |
| venv | `/home/pi/eldcare/eldcare-kb-manager/v2/.venv` |
| 数据目录 | `/home/pi/eldcare/eldcare-kb-manager/v2/data`（movies.db） |
| 媒体目录 | `/mnt/ztv/movies`（只读共享，指向 V1 同款片库） |
| 数据迁移 | V1 `movies.db` 中 32 部真实存在的电影已导入 V2 |
| 代码来源 | GitHub `zwa12345/eldcare`（本地 VS Code 与 WorkBuddy 双副本 push 后 pi05 clone） |

## 服务管理命令（pi05，user=pi）

```bash
systemctl --user status eldcare-v2.service   # 状态
systemctl --user restart eldcare-v2.service  # 重启
systemctl --user stop eldcare-v2.service     # 停止
journalctl --user -u eldcare-v2.service -f   # 实时日志
```

## 升级部署（代码更新后）

1. 本地把改动 push 到 GitHub：`git push origin main`
2. pi05 上更新代码 + 重启：
   ```bash
   cd /home/pi/eldcare && git pull origin main
   systemctl --user restart eldcare-v2.service
   ```
   或用一键脚本：
   ```bash
   # 本机执行（需 paramiko + 目标机器 creds）
   python scripts/deploy_pi05.py            # clone/pull + 依赖 + .env + 服务 + health
   python scripts/deploy_pi05.py --migrate  # 额外执行 V1→V2 数据迁移
   ```

## 关键验证（已通过）

```bash
curl http://127.0.0.1:8090/api/v2/health     # {"status":"ok","instance_id":"if-pi05",...}
curl http://127.0.0.1:8090/api/v2/library/stats  # total_movies: 32
# Range 流播放（206 + 精确字节）：
curl -H "Range: bytes=0-1048575" http://127.0.0.1:8090/api/v2/player/stream/1
```

## 数据迁移说明

V1 库在 `/home/pi/knowledgebase_project/kb_manager/home_theater/movies.db`（55 条记录，39 部 ready）。
迁移策略：仅迁移**文件真实存在于 `/mnt/ztv/movies`** 的电影（约 33 部，最终 32 部去重入库），
`file_path` 从相对 `movies/xxx.mp4` 转为绝对路径 `/mnt/ztv/movies/xxx.mp4`（V2 播放器按绝对路径读文件），
`video_url`(magnet) → V2 `magnet` 字段，`status: ready→active`。

迁移脚本：`scripts/migrate_v1_to_v2.py`（幂等，按 file_path 去重，可重复执行）。

> 注：V1 的 `has_subtitle` 等在 V2 模型里为 NOT NULL 且无默认值的列，迁移脚本显式补 0/'none'。
> 建议后续在 `app/models/movie.py` 给这些列补 `default`，避免 ORM 直接插入时踩坑。

## 待办/演进（骨架阶段后续）

- `app/services/` 目前为空：需实现 scanner（扫描 /mnt/ztv/movies 增量入库）、metadata(TMDB)、thumbnail、subtitle 等
- V1 的 22 条无本地文件的电影（如外部/已清理源）未迁移
- watch_history / search_history / categories 表尚未迁移
- 前端 PWA 已注册 SW，可离线壳
