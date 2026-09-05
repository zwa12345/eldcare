"""
Home Theater - Movie Crawler
支持爬取:
  1. 豆瓣电影 Top250 / 分类页面 / 搜索
  2. YTS.am 电影库 (76,000+ 电影，磁力/种子，genre/year/quality 筛选)
  3. TVMaze 剧集/电影搜索 (元数据+封面)
  4. BT 磁力搜索 (torrentgalaxy / sukebei)
  5. 本地文件夹扫描
"""
import os
import re
import time
import logging
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup
from security import validate_magnet
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
PROXY = None  # 或 {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

session = requests.Session()
session.headers.update(HEADERS)

# ========== 年份过滤规则 ==========
# 用户要求：未来爬虫的电影不要老电影，都要在 2010 年后的电影
MIN_YEAR = 2010

def is_recent_movie(movie: dict) -> bool:
    """年份过滤：只保留 2010 年后的电影。
    year 缺失（无法判断）时保留，避免误伤；明确 < 2010 的丢弃。"""
    year = movie.get('year')
    if year is None:
        return True
    return year >= MIN_YEAR

def set_proxy(proxy_url):
    global PROXY
    PROXY = proxy_url

def fetch(url, timeout=15, retry=3) -> BeautifulSoup | None:
    for attempt in range(retry):
        try:
            kwargs = {'headers': HEADERS, 'timeout': timeout}
            if PROXY:
                kwargs['proxies'] = {'http': PROXY, 'https': PROXY}
            resp = session.get(url, **kwargs)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return BeautifulSoup(resp.text, 'html.parser')
        except Exception as e:
            logger.warning(f'Fetch failed (attempt {attempt+1}/{retry}): {url} — {e}')
            time.sleep(2)
    return None

# ========== 豆瓣爬虫 ==========
def parse_douban_detail(url: str) -> dict | None:
    """解析豆瓣电影详情页（仅在需要时调用，建议优先用列表页数据）"""
    soup = fetch(url)
    if not soup:
        return None
    try:
        info = soup.find('div', id='info')
        info_text = info.get_text(separator=' ') if info else ''
        year_match = re.search(r'(\d{4})', info_text)
        rating_tag = soup.find('strong', class_='ll rating_num')
        rating = float(rating_tag.text.strip()) if rating_tag else 0.0
        title_tag = soup.find('span', property='v:itemreviewed')
        title = title_tag.text.strip() if title_tag else ''
        title_en = ''
        if ' / ' in title:
            parts = title.split(' / ')
            title = parts[0].strip()
            title_en = parts[1].strip() if len(parts) > 1 else ''
        elif '(' in title:
            title_en = re.sub(r'\(.*\)', '', title).strip()
        poster = soup.find('img', alt=title)
        poster_url = poster.get('src') if poster else ''
        summary_tag = soup.find('span', property='v:summary')
        summary = summary_tag.text.strip() if summary_tag else ''
        genre_tags = soup.find_all('span', property='v:genre')
        genres = ','.join(g.text.strip() for g in genre_tags)
        country_match = re.search(r'制片国家|地区.*?:(.*?)(?:年|片)', info_text)
        country = country_match.group(1).strip() if country_match else ''
        directors = re.search(r'导演.*?:(.*?)(?:主演|$)', info_text)
        director = directors.group(1).strip() if directors else ''
        actors = re.search(r'主演.*?:(.*?)(?:简介|$)', info_text)
        actors_text = actors.group(1).strip() if actors else ''
        return {
            'title': title,
            'title_en': title_en,
            'year': int(year_match.group(1)) if year_match else None,
            'poster': poster_url,
            'rating': rating,
            'genre': genres,
            'country': country,
            'director': director,
            'actors': actors_text,
            'summary': summary,
            'source': 'douban',
            'status': 'ready',
        }
    except Exception as e:
        logger.error(f'Failed to parse Douban detail: {url} — {e}')
        return None


def parse_douban_list_item(item) -> dict | None:
    """从豆瓣 Top250 列表页item中直接提取信息（不请求详情页，避免429）"""
    try:
        pic = item.find('div', class_='pic')
        a = pic.find('a') if pic else None
        href = a.get('href') if a else ''
        img = pic.find('img') if pic else None
        title = img.get('alt') if img else ''
        poster = img.get('src') if img else ''

        info_div = item.find('div', class_='info')
        bd = info_div.find('div', class_='bd') if info_div else None

        # 解析标题下方的信息行: "导演: xxx / 主演: xxx / 1994(中国大陆)"
        info_text = bd.get_text(separator=' ') if bd else ''

        # 提取年份
        year_match = re.search(r'(19|20)\d{2}', info_text)
        year = int(year_match.group()) if year_match else None

        # 提取评分（span.rating_num 直接在 item 下，不在 div.star 内）
        rating = 0.0
        rating_span = item.find('span', class_='rating_num')
        if rating_span:
            try:
                rating = float(rating_span.text.strip())
            except ValueError:
                pass

        # 提取导演/演员（暂时不解析详情页，留空）
        director = ''
        actors = ''

        return {
            'title': title,
            'title_en': '',
            'year': year,
            'poster': poster,
            'rating': rating,
            'genre': '',
            'country': '',
            'director': director,
            'actors': actors,
            'summary': '',
            'source': 'douban',
            'status': 'ready',
        }
    except Exception as e:
        logger.warning(f'Failed to parse list item: {e}')
        return None

def crawl_douban_top(page=0) -> list:
    """爬取豆瓣 Top250（每页25部）- 仅请求列表页，不请求详情页"""
    start = page * 25
    url = f'https://movie.douban.com/top250?start={start}'
    soup = fetch(url)
    if not soup:
        return []
    items = soup.find_all('div', class_='item')
    results = []
    for item in items:
        movie = parse_douban_list_item(item)
        if movie and is_recent_movie(movie):
            results.append(movie)
            logger.info(f'✓ {movie["title"]} ({movie.get("year", "?")}) rating={movie["rating"]}')
        elif movie:
            logger.info(f'⏭ 跳过老片（<{MIN_YEAR}）: {movie.get("title")} ({movie.get("year")})')
    return results

def search_douban(keyword: str, max_results=20) -> list:
    """搜索豆瓣"""
    url = f'https://movie.douban.com/subject_search?search_text={quote_plus(keyword)}&cat=1002'
    soup = fetch(url)
    if not soup:
        return []
    results = []
    items = soup.find_all('table', class_='tb_img')
    if not items:
        tables = soup.find_all('table')
        for table in tables:
            a = table.find('a')
            if not a or 'movie.douban.com/subject' not in (a.get('href') or ''):
                continue
            href = a.get('href')
            title = a.text.strip()
            img = table.find('img')
            poster = img.get('src') if img else ''
            results.append({'title': title, 'poster': poster, 'source': 'douban', 'href': href})
            if len(results) >= max_results:
                break
    for item in items[:max_results]:
        a = item.find('a')
        if not a:
            continue
        href = a.get('href', '')
        if 'movie.douban.com/subject' not in href:
            continue
        img = item.find('img')
        title = img.get('title') if img else a.text.strip()
        results.append({'title': title, 'poster': img.get('src') if img else '', 'source': 'douban', 'href': href})
    return results[:max_results]

# ========== YTS.am 电影库 (76,000+ 电影，支持磁力链) ==========
YTS_BASE = 'https://yts.am/api/v2/list_movies.json'

def _yts_params(limit=20, sort_by='seeds', genre=None, query_term=None,
                minimum_rating=None, year=None, quality=None):
    """构建 YTS API 参数"""
    p = {'limit': limit, 'sort_by': sort_by}
    if genre:      p['genre'] = genre
    if query_term:  p['query_term'] = query_term
    if minimum_rating: p['minimum_rating'] = minimum_rating
    if year:       p['year'] = year
    if quality:    p['quality'] = quality
    return p

def _build_magnet(title: str, hash_str: str) -> str:
    """从种子 hash 构建磁力链"""
    if not hash_str:
        return ''
    # YTS 的 hash 通常是 40 字符 SHA1
    return f'magnet:?xt=urn:btih:{hash_str}&dn={quote_plus(title)}'

def crawl_yts(genre=None, sort_by='seeds', limit=20, minimum_rating=None, year=None, quality=None, query_term=None) -> list:
    """爬取 YTS.am 电影列表 (不请求详情页，直接从列表提取磁力)"""
    params = _yts_params(limit=min(limit, 50), sort_by=sort_by,
                          genre=genre, minimum_rating=minimum_rating,
                          year=year, quality=quality, query_term=query_term)
    try:
        r = requests.get(YTS_BASE, params=params, headers=HEADERS, timeout=15)
        data = r.json()
        if data.get('status') != 'ok':
            return []
        movies_data = data.get('data', {}).get('movies', [])
        results = []
        for m in movies_data:
            torrents = m.get('torrents') or []
            primary = torrents[0] if torrents else {}
            # YTS magnet_url 通常是指向下载页的 URL，需要自己构建磁力
            torrent_hash = primary.get('hash', '')
            magnet = primary.get('magnet_url', '') or _build_magnet(m.get('title', ''), torrent_hash)

            # 安全检查：验证磁力链格式
            if magnet:
                check = validate_magnet(magnet)
                if not check['safe']:
                    logger.warning(f'YTS 磁力链安全检查失败 [{m.get("title")}]: {check["reason"]}')
                    continue  # 跳过不安全的磁力链
                if check['hash']:
                    torrent_hash = check['hash']  # 用标准化后的 hash

            if not is_recent_movie(m):
                logger.info(f'⏭ 跳过老片（<{MIN_YEAR}）: {m.get("title")} ({m.get("year")})')
                continue

            results.append({
                'title':       m.get('title', ''),
                'title_en':    m.get('title_english', ''),
                'year':        m.get('year'),
                'rating':      m.get('rating', 0.0),
                'genre':       ','.join(m.get('genres', [])),
                'poster':      m.get('medium_cover_image', ''),
                'summary':     m.get('summary', ''),
                'magnet':      magnet,
                'torrent_url': primary.get('url', ''),
                'file_size':   primary.get('size', ''),
                'quality':     primary.get('quality', ''),
                'seeds':       primary.get('seeds', 0),
                'peers':       primary.get('peers', 0),
                'source':      'yts',
            })
        return results
    except Exception as e:
        logger.warning(f'YTS crawl failed: {e}')
        return []

def search_yts(keyword: str, limit=20) -> list:
    """搜索 YTS 电影"""
    return crawl_yts(query_term=keyword, sort_by='seeds', limit=limit)

def crawl_yts_by_genre(genre: str, sort_by='rating', limit=20) -> list:
    """按类型爬取 YTS"""
    return crawl_yts(genre=genre.lower(), sort_by=sort_by, limit=limit)

def crawl_yts_top(limit=20) -> list:
    """YTS 热门/评分最高的电影"""
    return crawl_yts(sort_by='rating', limit=limit, minimum_rating=7)

# ========== TVMaze 剧集/电影元数据 ==========
TVMAZE_BASE = 'https://api.tvmaze.com'

def search_tvmaze(keyword: str, max_results=20) -> list:
    """搜索 TVMaze 剧集/电影"""
    try:
        r = requests.get(f'{TVMAZE_BASE}/search/shows?q={quote_plus(keyword)}',
                         headers=HEADERS, timeout=10)
        results = r.json()
        movies = []
        for item in results[:max_results]:
            show = item['show']
            summary = re.sub(r'<[^>]+>', '', show.get('summary') or '')[:200]
            img = show.get('image') or {}
            year = int(show['premiered'][:4]) if show.get('premiered') else None
            if not is_recent_movie({'year': year}):
                logger.info(f'⏭ 跳过老片（<{MIN_YEAR}）: {show.get("name")} ({year})')
                continue
            movies.append({
                'title':    show.get('name', ''),
                'year':     year,
                'rating':   show.get('rating', {}).get('average') or 0.0,
                'genre':    ','.join(show.get('genres', [])),
                'poster':   img.get('medium', ''),
                'summary':  summary,
                'country':  (show.get('network') or {}).get('country', {}).get('name', '') if show.get('network') else '',
                'status':   show.get('status', ''),
                'source':   'tvmaze',
            })
        return movies
    except Exception as e:
        logger.warning(f'TVMaze search failed: {e}')
        return []

def crawl_tvmaze_show(show_id: int) -> dict | None:
    """获取 TVMaze 剧集详情"""
    try:
        r = requests.get(f'{TVMAZE_BASE}/shows/{show_id}',
                          headers=HEADERS, timeout=10)
        show = r.json()
        summary = re.sub(r'<[^>]+>', '', show.get('summary') or '')[:300]
        img = show.get('image') or {}
        year = int(show['premiered'][:4]) if show.get('premiered') else None
        if not is_recent_movie({'year': year}):
            logger.info(f'⏭ 跳过老片（<{MIN_YEAR}）: {show.get("name")} ({year})')
            return None
        return {
            'title':   show.get('name', ''),
            'year':    year,
            'rating':  show.get('rating', {}).get('average') or 0.0,
            'genre':   ','.join(show.get('genres', [])),
            'poster':  img.get('original', '') or img.get('medium', ''),
            'summary': summary,
            'country': (show.get('network') or {}).get('country', {}).get('name', '') if show.get('network') else '',
            'source':  'tvmaze',
        }
    except Exception as e:
        logger.warning(f'TVMaze show fetch failed: {e}')
        return None

# ========== 高清电台 (已停用 - 返回 403) ==========
# 高清电台 gaoqing.fm 已于 2024 年停用，保留函数但永远返回空列表
def crawl_gaoqing_tv(page=1, category=None) -> list:
    """爬取高清电台电影分类"""
    cat_map = {'movie': '1', 'tv': '2', 'doc': '3', 'anime': '4'}
    cat_id = cat_map.get(category, '1') if category else '1'
    url = f'https://gaoqing.fm/list/{cat_id}?page={page}'
    soup = fetch(url)
    if not soup:
        return []
    results = []
    for item in soup.find_all('div', class_='movie-item'):
        try:
            a = item.find('a')
            href = a.get('href') if a else ''
            img = item.find('img')
            title = img.get('alt') if img else ''
            poster = img.get('src') if img else ''
            info = item.find('div', class_='movie-info')
            rating_text = info.text if info else ''
            rating = 0.0
            rating_match = re.search(r'(\d+\.?\d*)分', rating_text)
            if rating_match:
                rating = float(rating_match.group(1))
            if href:
                results.append({
                    'title': title,
                    'poster': poster,
                    'rating': rating,
                    'source': f'gaoqing:{urljoin("https://gaoqing.fm", href)}',
                })
        except Exception:
            pass
    return results

def get_gaoqing_download(url: str) -> str | None:
    """获取高清电台下载链接"""
    soup = fetch(url)
    if not soup:
        return None
    magnet = soup.find('a', class_='magnet')
    if magnet:
        return magnet.get('href')
    ed2k = soup.find('a', class_='ed2k')
    return ed2k.get('href') if ed2k else None

# ========== 本地扫描 ==========
def scan_local_folder(folder: str) -> list:
    """扫描本地文件夹中的视频文件"""
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.rmvb'}
    results = []
    if not os.path.exists(folder):
        logger.warning(f'Folder not found: {folder}')
        return results
    for root, _, files in os.walk(folder):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in video_exts:
                continue
            file_path = os.path.join(root, f)
            size = os.path.getsize(file_path)
            name = os.path.splitext(f)[0]
            title = re.sub(r'[\._]', ' ', name)
            year_match = re.search(r'(19|20)\d{2}', name)
            year = int(year_match.group()) if year_match else None
            results.append({
                'title': title,
                'year': year,
                'file_path': file_path,
                'file_size': size,
                'source': 'local',
                'status': 'ready',
            })
            logger.info(f'✓ {title} ({size // (1024*1024)}MB)')
    return results

# ========== BT / 磁力搜索 (通过 torrent search 站点) ==========
def search_bt(keyword: str, max_results=10) -> list:
    """通过 BT 搜索站搜索（按优先级尝试多个源）"""
    results = []

    # 优先: torrentgalaxy（通常可用，有磁力链）
    try:
        url = f'https://torrentgalaxy.su/torrents.php?search={quote_plus(keyword)}&sort=seeders&order=desc'
        soup = fetch(url, timeout=10)
        if soup:
            for row in soup.find_all('tr', class_='ttable'):
                try:
                    title_a = row.find('a', href=re.compile(r'/torrent/'))
                    if not title_a:
                        # 尝试在 title 属性中找
                        for a in row.find_all('a'):
                            t = a.get('title') or ''
                            if t and len(t) > 10:
                                title_a = a
                                break
                    title = title_a.get('title') or title_a.text.strip() if title_a else ''
                    if not title:
                        continue
                    magnet_a = row.find('a', href=re.compile(r'^magnet:'))
                    magnet = magnet_a.get('href') if magnet_a else ''
                    if not magnet:
                        # 尝试找磁力链接的其他方式
                        for a in row.find_all('a'):
                            href = a.get('href') or ''
                            if href.startswith('magnet:'):
                                magnet = href
                                break
                    if not magnet:
                        continue

                    # 安全检查：验证磁力链
                    check = validate_magnet(magnet)
                    if not check['safe']:
                        logger.warning(f'BT 磁力链安全检查失败 [{title[:30]}]: {check["reason"]}')
                        continue

                    size_tds = row.find_all('td')
                    size = ''
                    for td in size_tds:
                        txt = td.get_text(strip=True)
                        if re.search(r'\d+\.?\d*\s*[TG]B', txt, re.I):
                            size = txt
                            break
                    # 从标题提取年份，过滤老片（<2010）
                    year_match = re.search(r'(19|20)\d{2}', title)
                    year = int(year_match.group()) if year_match else None
                    if not is_recent_movie({'year': year}):
                        logger.info(f'⏭ 跳过老片（<{MIN_YEAR}）: {title.strip()[:40]} ({year})')
                        continue
                    results.append({
                        'title': title.strip(),
                        'magnet': magnet,
                        'size': size,
                        'year': year,
                        'source': 'bt:torrentgalaxy',
                    })
                    if len(results) >= max_results:
                        break
                except Exception:
                    pass
            if results:
                return results[:max_results]
    except Exception as e:
        logger.warning(f'torrentgalaxy failed: {e}')

    # 备选1: sukebei (Nyaa 镜像，更快)
    try:
        url = f'https://sukebei.nyaa.si/?f=0&c=0_0&q={quote_plus(keyword)}'
        soup = fetch(url, timeout=10)
        if soup:
            for row in soup.find_all('tr', class_='success'):
                try:
                    a = row.find('a', title=True)
                    if not a:
                        continue
                    title = a.get('title') or a.text.strip()
                    magnet_a = row.find('a', href=re.compile(r'^magnet:'))
                    magnet = magnet_a.get('href') if magnet_a else ''
                    if not magnet:
                        continue
                    size = row.find_all('td')[-1].get_text(strip=True)
                    year_match = re.search(r'(19|20)\d{2}', title)
                    year = int(year_match.group()) if year_match else None
                    if not is_recent_movie({'year': year}):
                        logger.info(f'⏭ 跳过老片（<{MIN_YEAR}）: {title.strip()[:40]} ({year})')
                        continue
                    results.append({
                        'title': title.strip(),
                        'magnet': magnet,
                        'size': size,
                        'year': year,
                        'source': 'bt:sukebei',
                    })
                    if len(results) >= max_results:
                        break
                except Exception:
                    pass
            if results:
                return results[:max_results]
    except Exception as e:
        logger.warning(f'sukebei failed: {e}')

    return results[:max_results]

# ========== 批量爬取入口 ==========
def crawl_all_douban_top(pages=10):
    """爬取多页豆瓣Top250"""
    all_movies = []
    for page in range(pages):
        logger.info(f'=== 爬取豆瓣 Top250 第 {page+1} 页 ===')
        movies = crawl_douban_top(page)
        all_movies.extend(movies)
        time.sleep(1)
    return all_movies

if __name__ == '__main__':
    # 测试：爬取豆瓣首页 Top25
    print('Testing Douban crawler...')
    movies = crawl_douban_top(0)
    for m in movies:
        print(f'  {m["title"]} ({m.get("year","?")}) ⭐{m["rating"]}')
    print(f'Total: {len(movies)}')
