#!/usr/bin/env python3
"""
批量下载中文字幕
使用 OpenSubtitles API 或 subliminal
"""

import os
import sqlite3
import subprocess
import time

# 电影列表
MOVIES = [
    (34, ' toys总动员5', 'Toy Story 5'),
    (35, '头脑特工队2', 'Inside Out 2'),
    (38, '神偷奶爸4', 'Despicable Me 4'),
    (41, '蜘蛛侠-纵横宇宙', 'Spider-Man Across the Spider-Verse'),
    (42, '蜘蛛侠-平行宇宙', 'Spider-Man Into the Spider-Verse'),
    (54, '卢卡', 'Luca'),
    (55, '魔法满屋', 'Encanto'),
    (63, '寻龙传说', 'Raya and the Last Dragon'),
    (65, '布鲁伊', 'Bluey'),
    (75, '机器人瓦力', 'WALL-E'),
]

def download_subliminal(title, video_path):
    """使用 subliminal 下载字幕"""
    try:
        cmd = ['subliminal', 'download', '-l', 'zhcn', video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except Exception as e:
        print(f"  subliminal 错误: {e}")
        return False

def download_zimuku(title, video_path):
    """使用 zimuku 网站下载"""
    # 简化版本
    return False

def main():
    db_path = '/home/pi/knowledgebase_project/kb_manager/home_theater/movies.db'
    video_dir = '/mnt/ztv/movies'
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    success = 0
    failed = []
    
    for mid, title, en_title in MOVIES:
        # 获取视频路径
        cur.execute('SELECT file_path FROM movies WHERE id=?', (mid,))
        row = cur.fetchone()
        if not row:
            continue
        
        video_path = f"{video_dir}/{row[0]}"
        print(f'\n处理: {title}')
        print(f'  视频: {video_path}')
        
        if not os.path.exists(video_path):
            print(f'  ✗ 视频文件不存在')
            failed.append((mid, title, '文件不存在'))
            continue
        
        # 尝试 subliminal
        print(f'  尝试 subliminal...')
        if download_subliminal(en_title, video_path):
            print(f'  ✓ 字幕下载成功')
            success += 1
        else:
            print(f'  ✗ subliminal 失败')
            failed.append((mid, title, 'subliminal失败'))
        
        time.sleep(1)  # 避免请求过快
    
    conn.close()
    
    print(f'\n=== 完成 ===')
    print(f'成功: {success}/{len(MOVIES)}')
    if failed:
        print(f'失败: {len(failed)}')
        for m in failed:
            print(f'  {m[0]}: {m[1]} - {m[2]}')

if __name__ == '__main__':
    main()
