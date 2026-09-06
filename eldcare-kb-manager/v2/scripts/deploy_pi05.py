#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eldcare-kb-manager V2 —— 在 if-pi05 (Debian/aarch64, user=pi) 一键部署脚本。

功能：
  1. clone/pull GitHub 仓库到 /home/pi/eldcare
  2. 创建 .venv 并安装依赖
  3. 写入 /home/pi/eldcare/eldcare-kb-manager/v2/.env（适配 pi05 master 节点）
  4. 注册并启动 systemd 用户服务 eldcare-v2.service（端口 8090，开机自启）
  5. 可选：把 V1 home_theater/movies.db 中真实存在的电影迁移进 V2（migrate_v1_to_v2.py）

用法（本机，需装 paramiko）：
  python deploy_pi05.py [--skip-install] [--migrate]

依赖环境变量或下方常量可覆盖。
"""
import argparse
import os
import sys

# ---- 可配置 ----
HOST = os.environ.get("PI_HOST", "100.64.0.21")
USER = os.environ.get("PI_USER", "pi")
PASS = os.environ.get("PI_PASS", "zwa_7571")
REPO = "https://github.com/zwa12345/eldcare.git"
DEPLOY_ROOT = "/home/pi/eldcare"
V2 = f"{DEPLOY_ROOT}/eldcare-kb-manager/v2"
SERVICE = "eldcare-v2.service"
PORT = 8090
V1_DB = "/home/pi/knowledgebase_project/kb_manager/home_theater/movies.db"

ENV_CONTENT = f"""# eldcare V2 - if-pi05 master 节点配置
ELDCARE_PORT={PORT}
ELDCARE_NODE_ROLE=master
ELDCARE_INSTANCE_ID=if-pi05
ELDCARE_DATA_DIR={V2}/data
ELDCARE_MOVIES_DIR=/mnt/ztv/movies
ELDCARE_LOG_DIR={V2}/data/logs
ELDCARE_LOG_LEVEL=INFO
ELDCARE_JWT_SECRET=eldcare-v2-pi05-deploy-2026
ELDCARE_JWT_TTL_HOURS=720
"""

SERVICE_CONTENT = f"""[Unit]
Description=ELDCARE Home Theater V2 (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory={V2}
ExecStart={V2}/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port {PORT}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""


def ssh_connect():
    import paramiko
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=15)
    return c


def run(c, cmd, timeout=180):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode(errors="replace").strip()
    e = err.read().decode(errors="replace").strip()
    return o, e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-install", action="store_true", help="跳过 pip install")
    ap.add_argument("--migrate", action="store_true", help="同时执行 V1→V2 数据迁移")
    args = ap.parse_args()

    c = ssh_connect()
    try:
        # 1. clone/pull
        print("[1/5] clone/pull 仓库 ...")
        o, _ = run(c, f"git -C {DEPLOY_ROOT} rev-parse --short HEAD 2>/dev/null")
        if o:
            run(c, f"cd {DEPLOY_ROOT} && git pull origin main 2>&1")
            print(f"  已 pull（HEAD {o} → 最新）")
        else:
            run(c, f"cd /home/pi && rm -rf eldcare eldcare_tmp && git clone --depth 1 {REPO} eldcare")
            print("  全新 clone 完成")

        # 2. venv + 依赖
        print("[2/5] venv + 依赖 ...")
        run(c, f"test -d {V2}/.venv || python3 -m venv {V2}/.venv")
        if not args.skip_install:
            run(c, f"{V2}/.venv/bin/pip install --upgrade pip -q")
            o, e = run(c, f"{V2}/.venv/bin/pip install -r {V2}/requirements.txt 2>&1 | tail -3", 400)
            print(f"  依赖安装: {o or 'OK'}")

        # 3. .env
        print("[3/5] 写 .env ...")
        sftp = c.open_sftp()
        with sftp.file(f"{V2}/.env", "w") as f:
            f.write(ENV_CONTENT)
        sftp.close()

        # 4. systemd 服务
        print(f"[4/5] systemd 服务 {SERVICE} ...")
        sftp = c.open_sftp()
        with sftp.file(f"/home/pi/.config/systemd/user/{SERVICE}", "w") as f:
            f.write(SERVICE_CONTENT)
        sftp.close()
        o, e = run(c, f"systemctl --user daemon-reload && systemctl --user enable {SERVICE} && systemctl --user restart {SERVICE} && sleep 3 && systemctl --user is-active {SERVICE}")
        print(f"  服务状态: {o}")

        # 健康检查
        o, _ = run(c, f"curl -s http://127.0.0.1:{PORT}/api/v2/health")
        print(f"  health: {o}")

        # 5. 可选迁移
        if args.migrate:
            print("[5/5] V1→V2 数据迁移 ...")
            sftp = c.open_sftp()
            sftp.put(os.path.join(os.path.dirname(__file__), "migrate_v1_to_v2.py"), "/tmp/migrate_v1_to_v2.py")
            sftp.close()
            o, e = run(c, "python3 /tmp/migrate_v1_to_v2.py", 60)
            print(o)

        print("\n部署完成。访问: http://<if-pi05-ip>:{0}  (V2 家庭影院)".format(PORT))
    finally:
        c.close()


if __name__ == "__main__":
    main()
