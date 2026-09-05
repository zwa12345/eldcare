#!/usr/bin/env python3
"""
磁力链下载工具

⚠️ 重要说明（2026-09-01 树莓派环境测试结论）:
  树莓派网络环境封锁了 Bittorrent 协议（libtorrent、transmission-cli 均无法
  连接 peers），但浏览器 WebRTC 可以穿透封锁。

  因此服务器端直接下载不可行，电影必须通过浏览器 WebTorrent 边下边播。

  使用方式：
    1. 打开 http://100.64.0.21:5001
    2. 点击任意电影进入播放器页面
    3. 浏览器自动通过 WebRTC 连接 BT 网络，边下载边播放

本文件保留作参考，或在有网络中转服务器时使用。
"""
import os
import sys
import time
import argparse

MOVIES_DIR = os.path.join(os.path.dirname(__file__), 'movies')


def download_magnet(magnet_uri, save_dir=MOVIES_DIR, port=6881):
    """
    下载磁力链到本地目录（需要网络环境支持 Bittorrent 协议）
    在树莓派上不可用，仅作参考
    """
    try:
        import libtorrent as lt
    except ImportError:
        print('❌ libtorrent 未安装: pip3 install libtorrent')
        sys.exit(1)

    os.makedirs(save_dir, exist_ok=True)
    print(f'🔗 磁力链: {magnet_uri[:80]}...')

    ses = lt.session()
    ses.listen_on(port, port + 10)

    handle = ses.add_torrent({
        'url': magnet_uri,
        'save_path': save_dir,
        'storage_mode': lt.storage_mode_t.storage_mode_sparse,
    })

    print(f'⏳ 等待种子信息...')
    start = time.time()
    while not handle.has_metadata():
        time.sleep(0.5)
        if time.time() - start > 90:
            raise TimeoutError('获取种子信息超时（90秒）')
        sys.stdout.write('.')
        sys.stdout.flush()

    info = handle.get_torrent_info()
    name = info.name()
    print(f'\n📦 片名: {name}  ({info.num_files()} 个文件)')
    return name


def get_movie(movie_id):
    sys.path.insert(0, os.path.dirname(__file__))
    import database as db
    return db.get_movie_by_id(movie_id)


def main():
    parser = argparse.ArgumentParser(description='下载电影到本地')
    parser.add_argument('movie_id', type=int, help='电影ID')
    parser.add_argument('--port', type=int, default=6881, help='监听端口')
    args = parser.parse_args()

    movie = get_movie(args.movie_id)
    if not movie:
        print(f'❌ 电影ID {args.movie_id} 不存在')
        sys.exit(1)

    magnet = movie.get('video_url') or movie.get('magnet')
    if not magnet or not magnet.startswith('magnet:'):
        print(f'❌ 该电影没有磁力链')
        sys.exit(1)

    print(f'🎬 电影: {movie["title"]} ({movie.get("year","未知")})')
    print(f'\n⚠️ 注意: 树莓派网络环境不支持服务器端 BT 下载')
    print(f'   请使用浏览器打开 http://100.64.0.21:5001 在线播放\n')

    try:
        filename = download_magnet(magnet, port=args.port)
        print(f'\n✅ 下载成功: {filename}')
        print(f'📂 保存位置: {MOVIES_DIR}/{filename}')
    except TimeoutError as e:
        print(f'\n❌ 超时: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ 下载失败: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
