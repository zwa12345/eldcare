"""
Home Theater - SQLite Database Module
电影数据存储：标题、封面、评分、分类、播放链接
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'movies.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            title_en TEXT,
            year INTEGER,
            poster TEXT,
            cover_url TEXT,
            rating REAL DEFAULT 0,
            genre TEXT,
            country TEXT,
            director TEXT,
            actors TEXT,
            summary TEXT,
            video_url TEXT,
            subtitle_url TEXT,
            file_path TEXT,
            file_size INTEGER DEFAULT 0,
            duration INTEGER DEFAULT 0,
            source TEXT,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_favorite INTEGER DEFAULT 0,
            is_bookmark INTEGER DEFAULT 0,
            tags TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            icon TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS watch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER,
            position INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 插入默认分类
    default_cats = [
        ('全部', 'all', '🎬', 0),
        ('动作', 'action', '💥', 1),
        ('喜剧', 'comedy', '😂', 2),
        ('科幻', 'scifi', '🚀', 3),
        ('爱情', 'romance', '💕', 4),
        ('悬疑', 'mystery', '🔍', 5),
        ('恐怖', 'horror', '👻', 6),
        ('纪录片', 'documentary', '📚', 7),
        ('国产', 'chinese', '🇨🇳', 8),
        ('欧美', 'western', '🎥', 9),
        ('日韩', 'asian', '🎌', 10),
        ('动漫', 'anime', '⚡', 11),
    ]
    for name, slug, icon, order in default_cats:
        c.execute('''INSERT OR IGNORE INTO categories (name, slug, icon, sort_order) VALUES (?,?,?,?)''',
                  (name, slug, icon, order))
    conn.commit()
    conn.close()

# ========== Movie CRUD ==========
def add_movie(movie: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO movies (title, title_en, year, poster, cover_url, rating, genre,
                           country, director, actors, summary, video_url, subtitle_url,
                           file_path, file_size, duration, source, tags, status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        movie.get('title'), movie.get('title_en'), movie.get('year'),
        movie.get('poster'), movie.get('cover_url'), movie.get('rating', 0),
        movie.get('genre'), movie.get('country'), movie.get('director'),
        movie.get('actors'), movie.get('summary'),
        movie.get('video_url') or movie.get('magnet'),  # magnet 写入 video_url 字段
        movie.get('subtitle_url'), movie.get('file_path'), movie.get('file_size', 0),
        movie.get('duration', 0), movie.get('source'), movie.get('tags'),
        movie.get('status', 'pending')
    ))
    movie_id = c.lastrowid
    conn.commit()
    conn.close()
    return movie_id

def get_movies(page=1, page_size=20, category=None, keyword=None, sort='updated_at', order='desc') -> dict:
    conn = get_conn()
    c = conn.cursor()
    where = ['status != "deleted"']
    params = []
    # category slug 转中文关键词
    cat_keyword_map = {
        'action': '动作', 'comedy': '喜剧', 'scifi': '科幻', 'romance': '爱情',
        'mystery': '悬疑', 'horror': '恐怖', 'documentary': '纪录片',
        'chinese': '国产', 'western': '欧美', 'asian': '日韩', 
        'anime': '动画', 'animation': '动画'
    }
    if category and category != 'all':
        # 先尝试精确匹配分类表
        c.execute('SELECT name FROM categories WHERE slug=?', (category,))
        row = c.fetchone()
        if row:
            where.append('genre LIKE ?')
            params.append(f'%{row[0]}%')
        elif category in cat_keyword_map:
            where.append('genre LIKE ?')
            params.append(f'%{cat_keyword_map[category]}%')
        else:
            where.append('genre LIKE ?')
            params.append(f'%{category}%')
    if keyword:
        where.append('(title LIKE ? OR title_en LIKE ? OR director LIKE ? OR actors LIKE ? OR genre LIKE ? OR year LIKE ? OR tags LIKE ? OR summary LIKE ?)')
        k = f'%{keyword}%'
        params.extend([k, k, k, k, k, k, k, k])
    where_clause = ' AND '.join(where) if where else '1=1'
    order_clause = f'{sort} {order}' if sort in ['rating','views','likes','created_at','updated_at','title','year','download_count'] else 'updated_at DESC'
    offset = (page - 1) * page_size
    c.execute(f'SELECT COUNT(*) FROM movies WHERE {where_clause}', params)
    total = c.fetchone()[0]
    c.execute(f'''SELECT * FROM movies WHERE {where_clause}
                  ORDER BY {order_clause} LIMIT ? OFFSET ?''',
              params + [page_size, offset])
    rows = c.fetchall()
    conn.close()
    return {
        'items': [dict(r) for r in rows],
        'total': total,
        'page': page,
        'page_size': page_size,
        'pages': (total + page_size - 1) // page_size
    }

def get_movie_by_id(movie_id: int) -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM movies WHERE id=?', (movie_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_movie(movie_id: int, data: dict):
    conn = get_conn()
    c = conn.cursor()
    fields = ', '.join(f'{k}=?' for k in data.keys())
    c.execute(f'UPDATE movies SET {fields}, updated_at=? WHERE id=?',
              list(data.values()) + [datetime.now().isoformat(), movie_id])
    conn.commit()
    conn.close()

def delete_movie(movie_id: int):
    update_movie(movie_id, {'status': 'deleted'})

def purge_movie(movie_id: int):
    """彻底删除：移除数据库行（实体文件由调用方负责）"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM movies WHERE id=?', (movie_id,))
    conn.commit()
    conn.close()

def increment_views(movie_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE movies SET views=views+1 WHERE id=?', (movie_id,))
    conn.commit()
    conn.close()

def toggle_favorite(movie_id: int) -> bool:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT is_favorite FROM movies WHERE id=?', (movie_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    new_val = 1 - row[0]
    c.execute('UPDATE movies SET is_favorite=? WHERE id=?', (new_val, movie_id))
    conn.commit()
    conn.close()
    return bool(new_val)

# ========== Categories ==========
def get_categories() -> list:
    """获取分类列表（含电影数量）"""
    conn = get_conn()
    c = conn.cursor()
    
    # 先获取所有分类
    c.execute('SELECT * FROM categories ORDER BY sort_order')
    categories = [dict(r) for r in c.fetchall()]
    
    # 统计每个分类的电影数量（基于 genre 字段匹配）
    c.execute('''SELECT genre FROM movies WHERE status = 'ready' ''')
    genre_counts = {}
    for row in c.fetchall():
        if row[0]:
            for g in row[0].split(','):  # 中文逗号分隔
                g = g.strip()
                if g:
                    genre_counts[g] = genre_counts.get(g, 0) + 1
    
    # 更新分类数量 - 支持多 genre 匹配
    # 映射：category.name(英文) -> genre 匹配关键词(中文)
    cat_name_map = {
        'all': ['全部'],        # 特殊处理
        'action': ['动作'], 'comedy': ['喜剧'], 'scifi': ['科幻'], 'romance': ['爱情'],
        'mystery': ['悬疑'], 'horror': ['恐怖'], 'documentary': ['纪录片', '纪录'],
        'chinese': ['国产'], 'western': ['欧美'], 'asian': ['日韩'], 'anime': ['动画', '动漫', '卡通'],
        'music': ['音乐', '演唱会']
    }
    for cat in categories:
        if cat['slug'] == 'all':
            c.execute("SELECT COUNT(*) FROM movies WHERE status = 'ready'")
            cat['count'] = c.fetchone()[0]
        else:
            # 按 slug 匹配
            match_names = cat_name_map.get(cat['slug'], [cat['name']])
            cat['count'] = 0
            c.execute("SELECT genre FROM movies WHERE status = 'ready'")
            for row in c.fetchall():
                if row[0]:
                    genres = [g.strip() for g in row[0].split(',')]
                    if any(m in genres for m in match_names):
                        cat['count'] += 1
    
    conn.close()
    return categories

def movie_count_by_category() -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT genre, COUNT(*) as cnt FROM movies
        WHERE status != 'deleted' GROUP BY genre
    ''')
    counts = {}
    for row in c.fetchall():
        for g in (row[0] or '').split(','):
            g = g.strip()
            if g:
                counts[g] = counts.get(g, 0) + row[1]
    conn.close()
    return counts

# ========== Watch History ==========
def save_watch_position(movie_id: int, position: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO watch_history (movie_id, position, updated_at)
                 VALUES (?,?,?)''', (movie_id, position, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_watch_position(movie_id: int) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT position FROM watch_history WHERE movie_id=?', (movie_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

# ========== Search History ==========
def add_search_keyword(keyword: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO search_history (keyword) VALUES (?)', (keyword,))
    conn.commit()
    conn.close()

def get_search_history(limit=10) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT DISTINCT keyword FROM search_history ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def clear_search_history():
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM search_history')
    conn.commit()
    conn.close()

# ========== Stats ==========
def get_stats() -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM movies WHERE status != "deleted"')
    total = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM movies WHERE status = "ready"')
    ready = c.fetchone()[0]
    c.execute('SELECT SUM(views) FROM movies WHERE status != "deleted"')
    views = c.fetchone()[0] or 0
    c.execute('SELECT SUM(file_size) FROM movies WHERE status != "deleted"')
    size = c.fetchone()[0] or 0
    conn.close()
    return {'total': total, 'ready': ready, 'views': views, 'size': size}

def get_top_rated(limit=10) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM movies WHERE status IN ("ready","pending") AND rating>0 ORDER BY rating DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_movies(limit=10) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM movies WHERE status IN ("ready","pending") ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_random_movies(n=6) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM movies WHERE status IN ("ready","pending") ORDER BY RANDOM() LIMIT ?', (n,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

init_db()
