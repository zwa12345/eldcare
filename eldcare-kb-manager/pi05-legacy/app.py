"""
Home Theater - Flask Web Application
移动端遥控 + 高清播放 + 电影搜索分类
"""
import os
import re
import uuid
import logging
import mimetypes
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, jsonify, send_from_directory,
    render_template, Response, stream_with_context
)
import database as db

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 * 1024  # 50GB max
app.config['MoviesFolder'] = os.path.join(os.path.dirname(__file__), 'movies')
app.config['ThumbFolder'] = os.path.join(os.path.dirname(__file__), 'static', 'thumbs')
app.config['SubtitleFolder'] = os.path.join(os.path.dirname(__file__), 'subtitles')
os.makedirs(app.config['MoviesFolder'], exist_ok=True)
os.makedirs(app.config['ThumbFolder'], exist_ok=True)
os.makedirs(app.config['SubtitleFolder'], exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# ========== CORS & Helpers ==========
def cors_json(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        data = f(*args, **kwargs)
        if isinstance(data, tuple):
            data = list(data)
            data[1] = {**data[1], 'Access-Control-Allow-Origin': '*'}
        elif isinstance(data, dict):
            data = jsonify(data)
            data.headers['Access-Control-Allow-Origin'] = '*'
        return data
    return decorated

def api_response(data=None, message='ok', code=0, **extra):
    resp = {'code': code, 'message': message, 'data': data}
    resp.update(extra)
    return jsonify(resp)

# ========== Page Routes ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/player/<int:movie_id>')
def player_page(movie_id):
    movie = db.get_movie_by_id(movie_id)
    if not movie:
        return "Movie not found", 404
    db.increment_views(movie_id)
    return render_template('player.html', movie=movie)

@app.route('/search')
def search_page():
    return render_template('search.html')

@app.route('/category/<slug>')
def category_page(slug):
    return render_template('category.html', slug=slug)

# ========== API: Movies ==========
@app.route('/api/movies')
def api_movies():
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    category = request.args.get('category')
    keyword = request.args.get('keyword')
    sort = request.args.get('sort', 'updated_at')
    order = request.args.get('order', 'desc')
    result = db.get_movies(page, page_size, category, keyword, sort, order)
    return api_response(result)

@app.route('/api/movie/<int:movie_id>')
def api_movie(movie_id):
    movie = db.get_movie_by_id(movie_id)
    if not movie:
        return api_response(code=404, message='Movie not found')
    return api_response(movie)

@app.route('/api/movie', methods=['POST'])
def api_add_movie():
    data = request.get_json() or {}
    movie_id = db.add_movie(data)
    return api_response({'id': movie_id}, message='Movie added')

@app.route('/api/movie/<int:movie_id>', methods=['PUT'])
def api_update_movie(movie_id):
    data = request.get_json() or {}
    db.update_movie(movie_id, data)
    return api_response(message='Movie updated')

@app.route('/api/movie/<int:movie_id>', methods=['DELETE'])
def api_delete_movie(movie_id):
    movie = db.get_movie_by_id(movie_id)
    if not movie:
        return api_response(code=404, message='Movie not found')
    purge = request.args.get('purge', '0') == '1'
    removed = []
    if purge:
        # 真删：删除实体文件（视频+字幕），再做路径安全检查
        movies_dir = os.path.realpath(app.config['MoviesFolder'])
        for key in ('file_path', 'subtitle_url'):
            p = movie.get(key)
            if not p:
                continue
            # 只允许删除 movies/ 目录内的本地文件，防止路径穿越/误删
            if p.startswith(('http://', 'https://', 'magnet:', 'magnetic:')):
                continue
            rp = os.path.realpath(p)
            if rp == movies_dir or not rp.startswith(movies_dir + os.sep):
                continue
            try:
                if os.path.isfile(rp):
                    os.remove(rp)
                    removed.append(rp)
            except OSError as e:
                log.warning('删除文件失败 %s: %s', rp, e)
        db.purge_movie(movie_id)
        msg = f'Movie purged, {len(removed)} file(s) removed'
    else:
        db.delete_movie(movie_id)
        msg = 'Movie deleted'
    return api_response({'removed': removed}, message=msg)

@app.route('/api/movie/<int:movie_id>/favorite', methods=['POST'])
def api_toggle_favorite(movie_id):
    ok = db.toggle_favorite(movie_id)
    return api_response({'is_favorite': ok}, message='Favorite toggled')

@app.route('/api/movies/stats')
def api_stats():
    return api_response(db.get_stats())

@app.route('/api/movies/top-rated')
def api_top_rated():
    return api_response(db.get_top_rated(10))

@app.route('/api/movies/recent')
def api_recent_movies():
    return api_response(db.get_recent_movies(10))

@app.route('/api/movies/random')
def api_random_movies():
    return api_response(db.get_random_movies(6))

@app.route('/api/movies/recommend')
def api_recommend():
    """智能推荐：评分最高 + 最近观看 + 随机发现"""
    top = db.get_top_rated(5)
    recent = db.get_recent_movies(5)
    random_movies = db.get_random_movies(5)
    combined = {m['id']: m for m in top + recent + random_movies}
    return api_response(list(combined.values())[:10])

# ========== API: Categories ==========
@app.route('/api/categories')
def api_categories():
    categories = db.get_categories()  # 已在 database.py 中计算好 count
    return api_response(categories)

# ========== API: Search ==========
@app.route('/api/search')
def api_search():
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return api_response(message='Keyword required', code=400)
    db.add_search_keyword(keyword)
    result = db.get_movies(page=1, page_size=50, keyword=keyword)
    return api_response(result)

@app.route('/api/search/history')
def api_search_history():
    return api_response(db.get_search_history(10))

@app.route('/api/search/history', methods=['DELETE'])
def api_clear_search_history():
    db.clear_search_history()
    return api_response(message='Search history cleared')

# ========== API: Watch History ==========
@app.route('/api/watch/position/<int:movie_id>')
def api_watch_position(movie_id):
    return api_response({'position': db.get_watch_position(movie_id)})

@app.route('/api/watch/position', methods=['POST'])
def api_save_watch_position():
    data = request.get_json() or {}
    db.save_watch_position(data.get('movie_id'), data.get('position', 0))
    return api_response(message='Position saved')

# ========== API: Crawler Control ==========
@app.route('/api/crawl/douban')
def api_crawl_douban():
    import crawler as cr
    page = int(request.args.get('page', 0))
    movies = cr.crawl_douban_top(page)
    added = 0
    for m in movies:
        try:
            db.add_movie(m)
            added += 1
        except Exception as e:
            log.warning(f'Add movie failed: {e}')
    return api_response({'added': added, 'total': len(movies)}, message=f'Crawled {len(movies)} movies, added {added}')

@app.route('/api/crawl/douban/all')
def api_crawl_douban_all():
    import crawler as cr
    import threading
    def bg():
        for page in range(10):
            log.info(f'Crawling Douban page {page+1}/10...')
            movies = cr.crawl_douban_top(page)
            for m in movies:
                try:
                    db.add_movie(m)
                except Exception:
                    pass
    threading.Thread(target=bg, daemon=True).start()
    return api_response(message='Crawl started in background')

@app.route('/api/crawl/local')
def api_crawl_local():
    folder = request.args.get('folder', app.config['MoviesFolder'])
    import crawler as cr
    movies = cr.scan_local_folder(folder)
    added = 0
    for m in movies:
        try:
            db.add_movie(m)
            added += 1
        except Exception as e:
            log.warning(f'Add movie failed: {e}')
    return api_response({'added': added, 'total': len(movies)}, message=f'Scanned {len(movies)} local movies')

@app.route('/api/crawl/bt')
def api_crawl_bt():
    keyword = request.args.get('q', '')
    if not keyword:
        return api_response(message='Keyword required', code=400)
    import crawler as cr
    results = cr.search_bt(keyword)
    return api_response(results, message=f'Found {len(results)} BT results')

# ========== API: Video Streaming ==========
@app.route('/api/video/<int:movie_id>/stream')
def api_video_stream(movie_id):
    movie = db.get_movie_by_id(movie_id)
    if not movie:
        return "Not found", 404
    video_path = movie.get('file_path') or ''
    if not video_path or not os.path.exists(video_path):
        return "Video file not found", 404
    return stream_video(video_path)

def stream_video(path):
    """HLS/MP4 分片流，支持 Chromecast/DLNA/浏览器直接播放"""
    file_size = os.path.getsize(path)
    range_header = request.headers.get('Range')
    if range_header:
        byte_start, byte_end = 0, None
        match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            byte_start = int(match.group(1))
            byte_end = int(match.group(2)) if match.group(2) else None
        # 越界处理：Range 起点超出文件大小 → 416，浏览器才能正确识别
        if byte_start >= file_size:
            resp = Response(status=416)
            resp.headers['Content-Range'] = f'bytes */{file_size}'
            resp.headers['Accept-Ranges'] = 'bytes'
            return resp
        if byte_end is None or byte_end >= file_size:
            byte_end = file_size - 1
        length = byte_end - byte_start + 1
        def generate():
            with open(path, 'rb') as f:
                f.seek(byte_start)
                remaining = length
                chunk_size = 1024 * 1024  # 1MB
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        resp = Response(generate(), status=206, mimetype=mimetypes.guess_type(path)[0] or 'video/mp4')
        resp.headers['Content-Range'] = f'bytes {byte_start}-{byte_end}/{file_size}'
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = length
        return resp
    else:
        def generate():
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
        resp = Response(generate(), mimetype=mimetypes.guess_type(path)[0] or 'video/mp4')
        # 关键：无 Range 请求也要声明 Accept-Ranges，否则部分浏览器禁用进度条拖动
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = file_size
        return resp

@app.route('/api/video/<int:movie_id>/subtitle')
def api_subtitle(movie_id):
    """字幕下载代理，解决跨域问题；本地字幕直接读取"""
    movie = db.get_movie_by_id(movie_id)
    if not movie or not movie.get('subtitle_url'):
        return "No subtitle", 404
    sub = movie['subtitle_url']
    mimetype = 'application/x-srt' if sub.lower().endswith('.srt') else 'text/vtt'
    # 本地文件直接读取
    if os.path.exists(sub):
        try:
            with open(sub, 'rb') as f:
                content = f.read()
            # 检测编码，srt 常见 UTF-8 / GBK
            if sub.lower().endswith('.srt'):
                try:
                    text = content.decode('utf-8')
                except UnicodeDecodeError:
                    text = content.decode('gbk', errors='replace')
                content = text.encode('utf-8')
            return Response(content, mimetype=mimetype)
        except Exception as e:
            return str(e), 502
    try:
        import requests as req
        r = req.get(sub, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        return Response(r.content, mimetype=mimetype)
    except Exception as e:
        return str(e), 502

# ========== API: Poster/Thumbnails ==========
@app.route('/api/proxy/poster')
def api_proxy_poster():
    """封面图代理，解决跨域"""
    url = request.args.get('url')
    if not url:
        return "url required", 400
    try:
        import requests as req
        r = req.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10, stream=True)
        return Response(r.iter_content(8192), mimetype=r.headers.get('Content-Type', 'image/jpeg'))
    except Exception as e:
        return str(e), 502

# ========== Error Handlers ==========
@app.errorhandler(404)
def not_found(e):
    return api_response(code=404, message='Resource not found')

@app.errorhandler(500)
def server_error(e):
    return api_response(code=500, message='Internal server error')

# ========== Startup ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
