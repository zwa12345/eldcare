#!/usr/bin/env python3
"""
自动下载任务：爬虫 → 中继下载 → 本机下载
每半小时运行一次
"""
import os
import sys
import time
import json
import subprocess
import requests
import sqlite3
from urllib.parse import quote

# 配置
RELAY_HOST = "47.253.53.228"
RELAY_HTTP_PORT = 8080
LOCAL_MOVIE_DIR = "/mnt/ztv/movies"
DB_PATH = "/home/pi/knowledgebase_project/kb_manager/home_theater/movies.db"
LOG_FILE = "/home/pi/knowledgebase_project/kb_manager/home_theater/auto_download.log"

# 中继电影存储目录
RELAY_MOVIE_BASE = "/home/admin"

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def run_ssh(cmd):
    """执行远程 SSH 命令"""
    result = subprocess.run(
        f'PW=$(openssl pkeyutl -decrypt -inkey ~/.secrets/relay_key.pem -in ~/.secrets/relay_pass.enc) && sshpass -p "$PW" ssh -o StrictHostKeyChecking=no admin@{RELAY_HOST} "{cmd}"',
        shell=True, capture_output=True, text=True
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def check_relay_disk_space():
    """检查中继磁盘空间"""
    out, _, rc = run_ssh("df -h /home/admin | tail -1")
    if rc == 0:
        log(f"中继磁盘: {out}")
        # 提取可用空间
        parts = out.split()
        if len(parts) >= 4:
            avail = parts[3]
            if 'G' in avail:
                gb = float(avail.replace('G', ''))
                if gb < 5:
                    log(f"⚠️ 中继空间不足: {avail}")
                    return False
    return True

def ensure_relay_http():
    """确保中继 HTTP 服务运行"""
    out, _, rc = run_ssh(f"netstat -tlnp | grep ':{RELAY_HTTP_PORT}'")
    if not out:
        log("启动中继 HTTP 服务...")
        run_ssh(f"cd /home/admin && nohup python3 -m http.server {RELAY_HTTP_PORT} > /tmp/http.log 2>&1 &")
        time.sleep(2)
    # 验证
    try:
        r = requests.get(f"http://{RELAY_HOST}:{RELAY_HTTP_PORT}/", timeout=5)
        if r.status_code == 200:
            log("✓ 中继 HTTP 服务正常")
            return True
    except:
        pass
    log("✗ 中继 HTTP 服务启动失败")
    return False

def get_magnet_hash(magnet):
    """从磁力链提取 hash"""
    if not magnet:
        return None
    if magnet.startswith("magnet:"):
        import re
        m = re.search(r'xt=urn:btih:([a-fA-F0-9]{32,40})', magnet)
        if m:
            return m.group(1).lower()
    return None

def download_to_relay(title, magnet, output_dir):
    """使用 libtorrent 下载到中继"""
    # 创建输出目录
    safe_name = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
    out_path = f"{RELAY_MOVIE_BASE}/out_{safe_name.replace(' ', '_')}"
    
    run_ssh(f"mkdir -p {out_path}")
    
    # 复制已存在的 relay_lt.py 到中继
    run_ssh("mkdir -p /home/admin/.hermes")
    subprocess.run(
        'PW=$(openssl pkeyutl -decrypt -inkey ~/.secrets/relay_key.pem -in ~/.secrets/relay_pass.enc) && sshpass -p "$PW" scp -o StrictHostKeyChecking=no /home/pi/knowledgebase_project/kb_manager/home_theater/relay_lt.py admin@47.253.53.228:/tmp/relay_lt.py',
        shell=True, capture_output=True
    )
    
    # 运行下载脚本
    run_ssh(f"nohup python3 /tmp/relay_lt.py '{magnet}' '{out_path}' > /tmp/lt.log 2>&1 &")
    
    log(f"开始下载到中继: {title} -> {out_path}")
    return out_path

def wait_relay_download(out_path, timeout=1800, check_interval=30):
    """监控中继下载完成"""
    log(f"等待中继下载完成: {out_path}")
    start = time.time()
    while time.time() - start < timeout:
        # 检查是否有 .mp4 文件且大小稳定
        out, _, _ = run_ssh(f"find {out_path} -name '*.mp4' -type f -size +100M")
        if out:
            # 等待文件大小稳定
            time.sleep(10)
            out2, _, _ = run_ssh(f"find {out_path} -name '*.mp4' -type f -size +100M")
            if out2:
                log(f"✓ 中继下载完成: {out}")
                return True
        
        # 检查 libtorrent 进程
        proc, _, _ = run_ssh(f"pgrep -f 'libtorrent'")
        if not proc:
            log("⚠️ libtorrent 进程已结束")
            # 再检查一次文件
            out, _, _ = run_ssh(f"find {out_path} -name '*.mp4' -type f")
            if out:
                log(f"✓ 文件存在: {out}")
                return True
            return False
        
        # 显示进度
        log_out, _, _ = run_ssh("tail -1 /tmp/lt.log 2>/dev/null")
        if log_out:
            log(f"进度: {log_out}")
        
        time.sleep(check_interval)
    
    log("✗ 中继下载超时")
    return False

def get_movie_files(out_path):
    """获取中继下载目录中的电影文件 (返回完整路径列表)"""
    out, _, _ = run_ssh(f"find {out_path} -name '*.mp4' -o -name '*.mkv' -type f")
    if out:
        return [f"/{f.lstrip('/')}" for f in out.split('\n') if f]
    return []

def download_to_local(relay_out_dir, local_name):
    """从 relay HTTP 下载到本机 (单线程)
    
    relay_out_dir: 中继输出目录, 如 /home/admin/out_The_Day_of_the_Doctor
    返回: 实际电影文件路径 (如 /home/admin/out_The_Day_of_the_Doctor/子目录/xxx.mp4)
    """
    # 查找实际电影文件 (可能有子目录)
    movie_files = get_movie_files(relay_out_dir)
    if not movie_files:
        log(f"✗ 中继目录中未找到电影文件: {relay_out_dir}")
        return None
    
    relay_path = movie_files[0]  # 取第一个
    filename = os.path.basename(relay_path)
    
    # 修复路径: /home/admin/out_The_Day -> /out_The_Day/子目录/文件名 (无需 admin 前缀)
    parent_dir = os.path.basename(relay_out_dir)  # out_The_Day_of_the_Doctor
    subdir = os.path.basename(os.path.dirname(relay_path))  # 子目录名
    # 使用 quote() 对路径进行 URL 编码
    url = f"http://{RELAY_HOST}:{RELAY_HTTP_PORT}/{quote(parent_dir)}/{quote(subdir)}/{quote(filename)}"
    
    local_path = f"{LOCAL_MOVIE_DIR}/{local_name}"
    
    log(f"下载到本机: {url}")
    log(f"目标路径: {local_path}")
    
    # 使用单线程下载 (Python http.server 不支持多线程)
    # 添加超时和重试
    # 注意: 用单引号包围 URL, 关闭 curl globbing 以处理文件名中的 [] 字符
    result = subprocess.run(
        f"curl -s -g --connect-timeout 60 --max-time 1800 -o '{local_path}' '{url}'",
        shell=True, capture_output=True, text=True
    )
    
    if result.returncode != 0:
        log(f"✗ curl 错误: {result.stderr}")
    
    if os.path.exists(local_path):
        size = os.path.getsize(local_path)
        # 检查文件是否为有效视频 (不是 HTML 错误页面)
        if size < 1000:
            with open(local_path, 'r', errors='ignore') as f:
                content = f.read(100)
                if '<html' in content.lower():
                    log(f"✗ 下载得到 HTML 错误页面，删除文件")
                    os.remove(local_path)
                    return None
        log(f"✓ 下载完成: {local_path} ({size/1024/1024:.1f}MB)")
        return local_path
    else:
        log(f"✗ 下载失败")
        return None

def add_to_database(title, title_en, year, director, actors, genre, file_path, file_size):
    """添加到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('''INSERT INTO movies 
            (title, title_en, year, poster, cover_url, rating, genre, country, director, actors, 
             summary, file_path, file_size, duration, source, views, likes, status, tags, is_favorite) 
            VALUES (?, ?, ?, '', '', 0, ?, '', ?, ?, '', ?, ?, 0, 'yts', 0, 0, 'ready', '', 0)''',
            (title, title_en, year, genre, director, actors, file_path, file_size))
        conn.commit()
        conn.close()
        log(f"✓ 已添加到数据库: {title}")
        return True
    except Exception as e:
        log(f"✗ 数据库错误: {e}")
        return False

def crawl_and_download():
    """爬取并下载电影"""
    log("=" * 50)
    log("开始自动下载任务")
    
    # 1. 检查中继空间
    if not check_relay_disk_space():
        log("中继空间不足，跳过")
        return
    
    # 2. 确保 HTTP 服务
    if not ensure_relay_http():
        log("中继 HTTP 服务不可用，跳过")
        return
    
    # 3. 先处理 pending 列表中有 magnet 的电影
    log("检查 pending 电影...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, title, title_en, year, video_url FROM movies WHERE status='pending' AND video_url IS NOT NULL AND video_url LIKE 'magnet:%'")
    pending_movies = cur.fetchall()
    if pending_movies:
        log(f"找到 {len(pending_movies)} 部 pending 电影")
        for pm in pending_movies:
            movie_id, title, title_en, year, magnet = pm
            log(f"处理 pending: {title} ({title_en})")
            # 下载到中继
            safe_name = "".join(c for c in title_en if c.isalnum() or c in " -_").strip()[:50] if title_en else title
            out_path = f"{RELAY_MOVIE_BASE}/out_{safe_name.replace(' ', '_')}"
            run_ssh(f"mkdir -p {out_path}")
            
            # 复制 relay_lt.py
            run_ssh("mkdir -p /home/admin/.hermes")
            subprocess.run(
                'PW=$(openssl pkeyutl -decrypt -inkey ~/.secrets/relay_key.pem -in ~/.secrets/relay_pass.enc) && sshpass -p "$PW" scp -o StrictHostKeyChecking=no /home/pi/knowledgebase_project/kb_manager/home_theater/relay_lt.py admin@47.253.53.228:/tmp/relay_lt.py',
                shell=True, capture_output=True
            )
            
            # 启动下载
            run_ssh(f"nohup python3 /tmp/relay_lt.py '{magnet}' '{out_path}' > /tmp/lt.log 2>&1 &")
            
            # 等待下载完成
            if wait_relay_download(out_path, timeout=1800):
                files = get_movie_files(out_path)
                if files:
                    relay_file = files[0]
                    ext = os.path.splitext(relay_file)[1] or '.mp4'
                    local_name = f"{title_en}{ext}".replace(" ", ".") if title_en else f"{title}{ext}"
                    local_path = download_to_local(out_path, local_name)
                    
                    if local_path and os.path.exists(local_path):
                        size = os.path.getsize(local_path)
                        if size < 10 * 1024 * 1024:
                            log(f"✗ 文件太小 ({size/1024/1024:.1f}MB)，删除")
                            os.remove(local_path)
                        else:
                            log(f"✓ 下载完成: {size/1024/1024:.1f}MB")
                            # 更新数据库状态
                            cur.execute("UPDATE movies SET status='ready', file_path=? WHERE id=?", (local_path, movie_id))
                            conn.commit()
                            log(f"✓ 已更新数据库: {title}")
            
            # 只处理一部 pending 电影
            break
    conn.close()
    
    # 4. 爬取 YTS 高分电影
    log("爬取 YTS 热门电影...")
    try:
        sys.path.insert(0, "/home/pi/knowledgebase_project/kb_manager/home_theater")
        from crawler import crawl_yts_top
        movies = crawl_yts_top(limit=10)
        log(f"获取到 {len(movies)} 部候选电影")
    except Exception as e:
        log(f"爬取失败: {e}")
        return
    
    # 4. 过滤已下载的电影
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT title_en, file_path FROM movies WHERE status='ready' AND title_en IS NOT NULL")
    rows = cur.fetchall() or []
    existing = {row[0].lower(): row[1] for row in rows if row[0]}
    conn.close()
    
    # 5. 选择一部电影下载 (使用模糊匹配以处理标题微小差异)
    for m in movies:
        title_en = m.get('title_en', '')
        if not title_en:
            title_en = m.get('title', '')
        
        # 精确匹配或模糊匹配（去除标点后比较）
        title_clean = title_en.lower().replace(',', '').replace(':', '').replace('-', ' ')
        
        is_downloaded = False
        for existing_title in existing:
            existing_clean = existing_title.replace(',', '').replace(':', '').replace('-', ' ')
            # 精确匹配或一个包含另一个
            if (title_en.lower() == existing_title or 
                existing_clean in title_clean or 
                title_clean in existing_clean):
                is_downloaded = True
                log(f"跳过已下载: {title_en} (匹配: {existing_title})")
                break
        
        if is_downloaded:
            continue
        
        magnet = m.get('magnet', '')
        if not magnet:
            continue
        
        title = m.get('title', title_en)
        log(f"选择下载: {title} ({title_en})")
        
        # 下载到中继
        out_path = download_to_relay(title_en, magnet, RELAY_MOVIE_BASE)
        
        # 等待下载完成
        if wait_relay_download(out_path, timeout=1800):
            files = get_movie_files(out_path)
            if files:
                relay_file = files[0]
                # 下载到本机 - 使用实际文件扩展名
                ext = os.path.splitext(relay_file)[1] or '.mp4'
                local_name = f"{title_en}{ext}".replace(" ", ".")
                local_path = download_to_local(out_path, local_name)
                
                if local_path and os.path.exists(local_path):
                    size = os.path.getsize(local_path)
                    # 检查文件大小是否合理 (至少 10MB)
                    if size < 10 * 1024 * 1024:
                        log(f"✗ 文件太小 ({size/1024/1024:.1f}MB)，可能是下载不完整，删除")
                        os.remove(local_path)
                    else:
                        log(f"✓ 文件下载完成，大小: {size/1024/1024:.1f}MB")
                        add_to_database(
                            title, title_en, m.get('year'),
                            m.get('director', ''), m.get('actors', ''),
                            m.get('genre', ''), local_path, size
                        )
        
        # 只下载一部
        break
    
    log("任务完成")

if __name__ == "__main__":
    crawl_and_download()
