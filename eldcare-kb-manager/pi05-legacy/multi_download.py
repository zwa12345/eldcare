#!/usr/bin/env python3
"""中继多线程下载脚本"""
import os
import sys
import requests
import threading
from urllib.parse import quote

def download_chunk(url, start, end, file_path, thread_id):
    """下载分片"""
    headers = {'Range': f'bytes={start}-{end}'}
    try:
        r = requests.get(url, headers=headers, timeout=60, stream=True)
        with open(f"{file_path}.part{thread_id}", 'wb') as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        print(f"Thread {thread_id} 完成: {start}-{end}")
    except Exception as e:
        print(f"Thread {thread_id} 错误: {e}")

def multi_download(url, local_path, num_threads=4):
    """多线程下载"""
    # 获取文件大小
    r = requests.head(url, timeout=30)
    file_size = int(r.headers.get('content-length', 0))
    print(f"文件大小: {file_size/1024/1024:.1f} MB")
    
    # 创建空文件
    with open(local_path, 'wb') as f:
        pass
    
    # 计算分片
    chunk_size = file_size // num_threads
    threads = []
    
    for i in range(num_threads):
        start = i * chunk_size
        end = start + chunk_size - 1 if i < num_threads - 1 else file_size - 1
        t = threading.Thread(target=download_chunk, args=(url, start, end, local_path, i))
        threads.append(t)
        t.start()
    
    # 等待完成
    for t in threads:
        t.join()
    
    # 合并分片
    print("合并分片...")
    with open(local_path, 'wb') as fout:
        for i in range(num_threads):
            with open(f"{local_path}.part{i}", 'rb') as fin:
                fout.write(fin.read())
            os.remove(f"{local_path}.part{i}")
    
    print(f"下载完成: {local_path}")
    return local_path

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: multi_download.py <url> <local_path> [threads]")
        sys.exit(1)
    
    url = sys.argv[1]
    local_path = sys.argv[2]
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    
    multi_download(url, local_path, threads)
