#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B站电影爬虫 - 获取电影信息"""
import urllib.request, urllib.parse, json, re, ssl, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

def get_movies_by_page(page=1, pagesize=20):
    """获取B站电影列表"""
    url = f"https://api.bilibili.com/x/web-interface/ranking/v2?rid=23&type=fc&pn={page}&ps={pagesize}"
    req = urllib.request.Request(url, headers=UA)
    try:
        data = urllib.request.urlopen(req, timeout=15, context=ctx).read()
        result = json.loads(data)
        if result.get('code') == 0:
            return result.get('data', {}).get('list', [])
    except Exception as e:
        print(f"Error: {e}")
    return []

def get_movie_detail(bvid):
    """获取电影详情"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    req = urllib.request.Request(url, headers=UA)
    try:
        data = urllib.request.urlopen(req, timeout=10, context=ctx).read()
        result = json.loads(data)
        if result.get('code') == 0:
            return result.get('data', {})
    except:
        pass
    return {}

def filter_2010_plus(movies):
    """筛选2010年及以后的电影"""
    filtered = []
    for m in movies:
        title = m.get('title', '')
        # 尝试从标题或subtitle获取年份
        year_match = re.search(r'(19\d{2}|20\d{2})', title)
        year = int(year_match.group(1)) if year_match else 0
        if year >= 2010:
            filtered.append(m)
    return filtered

if __name__ == "__main__":
    print("=== B站电影爬虫 ===")
    all_movies = []
    
    # 获取前3页
    for page in range(1, 4):
        print(f"获取第 {page} 页...")
        movies = get_movies_by_page(page)
        all_movies.extend(movies)
        time.sleep(0.5)
    
    print(f"\n共获取 {len(all_movies)} 部电影")
    
    # 筛选2010年及以后的
    recent = filter_2010_plus(all_movies)
    print(f"2010年及以后: {len(recent)} 部")
    
    # 输出前20部
    print("\n前20部热门电影:")
    for i, m in enumerate(all_movies[:20]):
        title = m.get('title', '')
        play = m.get('stat', {}).get('view', 0)
        bvid = m.get('bvid', '')
        print(f"  {i+1}. {title} (播放:{play//10000}万) BV:{bvid}")
