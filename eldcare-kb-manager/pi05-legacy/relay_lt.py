#!/usr/bin/env python3
"""中继下载脚本 - 上传到中继服务器运行"""
import libtorrent as lt
import time
import sys

if len(sys.argv) < 3:
    print("用法: relay_lt.py <magnet> <save_path>")
    sys.exit(1)

magnet = sys.argv[1]
save_path = sys.argv[2]

print("初始化 libtorrent...")

ses = lt.session()
ses.listen_on(6881, 6891)

# 使用 add_torrent_params
atp = lt.add_torrent_params()
atp.save_path = save_path
atp.url = magnet

handle = ses.add_torrent(atp)
print("开始下载:", handle.name())

while not handle.is_seed():
    st = handle.status()
    rate = st.download_rate / 1024 / 1024 if st.download_rate else 0
    pct = st.progress * 100
    print("%.1f MB/s %.1f%%" % (rate, pct))
    time.sleep(30)

print("下载完成!")
