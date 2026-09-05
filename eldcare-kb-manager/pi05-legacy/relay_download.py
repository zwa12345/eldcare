#!/usr/bin/env python3
"""
中继下载器：使用 libtorrent 下载磁力到中继服务器
在后台运行并输出进度
"""
import sys
import os
import time

# 检查 libtorrent
try:
    import libtorrent as lt
except ImportError:
    print("Error: libtorrent not installed")
    sys.exit(1)

def download_magnet(magnet_url, save_path):
    """使用 libtorrent 下载磁力"""
    print(f"初始化下载: {magnet_url}")
    print(f"保存路径: {save_path}")
    
    # 创建 session
    ses = lt.session()
    ses.listen_on(6881, 6891)
    
    # 添加 torrent
    params = {
        "save_path": save_path,
        "url": magnet_url,
    }
    
    handle = ses.add_torrent(params)
    
    print(f"开始下载: {handle.name()}")
    
    # 等待下载完成
    while not handle.is_seed():
        status = handle.handle.status()
        print(f"下载: {status.download_rate/1024/1024:.1f} MB/s, 进度: {status.progress*100:.1f}%")
        time.sleep(30)
    
    print(f"下载完成: {handle.name()}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: relay_download.py <magnet_url> <save_path>")
        sys.exit(1)
    
    magnet_url = sys.argv[1]
    save_path = sys.argv[2]
    
    # 确保目录存在
    os.makedirs(save_path, exist_ok=True)
    
    try:
        download_magnet(magnet_url, save_path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
