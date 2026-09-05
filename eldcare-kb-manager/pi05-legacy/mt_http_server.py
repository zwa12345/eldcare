#!/usr/bin/env python3
"""多线程 HTTP 服务器"""
import asyncio
import os
from aiohttp import web

async def serve_file(request):
    path = request.app['root'] + request.path
    if os.path.isdir(path):
        # 目录索引
        files = os.listdir(path)
        body = "<h1>Directory</h1><ul>"
        for f in sorted(files):
            body += f'<li><a href="{request.path}/{f}">{f}</a></li>'
        body += "</ul>"
        return web.Response(text=body, content_type='text/html')
    
    if not os.path.exists(path):
        return web.Response(status=404, text="Not Found")
    
    # 返回文件，支持 Range 请求
    file_size = os.path.getsize(path)
    range_header = request.headers.get('Range')
    
    if range_header:
        # 解析 Range
        range_spec = range_header.replace('bytes=', '')
        start, end = range_spec.split('-')
        start = int(start) if start else 0
        end = int(end) if end else file_size - 1
        
        with open(path, 'rb') as f:
            f.seek(start)
            data = f.read(end - start + 1)
        
        return web.Response(
            body=data,
            status=206,
            headers={
                'Content-Range': f'bytes {start}-{end}/{file_size}',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(end - start + 1),
                'Content-Type': 'application/octet-stream'
            }
        )
    else:
        with open(path, 'rb') as f:
            data = f.read()
        return web.Response(
            body=data,
            headers={
                'Accept-Ranges': 'bytes',
                'Content-Length': str(file_size),
                'Content-Type': 'application/octet-stream'
            }
        )

def run_server(port, root_dir):
    app = web.Application()
    app['root'] = root_dir
    app.router.add_get('/{path:.*}', serve_file)
    app.router.add_get('/', serve_file)
    web.run_app(app, host='0.0.0.0', port=port, print=None)

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    root = sys.argv[2] if len(sys.argv) > 2 else '/home/admin'
    run_server(port, root)
