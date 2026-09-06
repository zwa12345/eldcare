# -*- coding: utf-8 -*-
"""
把 V1 movies.db 中真实存在的电影迁移到 V2 movies 表。
字段映射 V1->V2, file_path 转绝对路径, status: ready->active。
幂等: 已存在同 file_path 则跳过。
"""
import sqlite3, os

V1_DB = "/home/pi/knowledgebase_project/kb_manager/home_theater/movies.db"
V2_DB = "/home/pi/eldcare/eldcare-kb-manager/v2/data/movies.db"
MOVIES_ROOT = "/mnt/ztv/movies"

def resolve_v2_path(fp):
    """V1 相对路径 -> V2 绝对可播放路径"""
    if not fp:
        return None
    if fp.startswith("movies/"):
        return os.path.join(MOVIES_ROOT, fp[len("movies/"):])
    if os.path.isabs(fp):
        return fp
    return os.path.join(MOVIES_ROOT, os.path.basename(fp))

def main():
    con1 = sqlite3.connect(V1_DB)
    con1.row_factory = sqlite3.Row
    cur1 = con1.cursor()

    con2 = sqlite3.connect(V2_DB)
    cur2 = con2.cursor()

    # V2 现有 path 集合(用于幂等)
    existing = {r[0] for r in cur2.execute("SELECT file_path FROM movies")}
    print(f"V2 现有电影: {len(existing)}")

    rows = cur1.execute("SELECT * FROM movies ORDER BY id").fetchall()
    inserted = 0
    skipped_no_file = 0
    skipped_dup = 0
    errors = []

    for r in rows:
        v2path = resolve_v2_path(r["file_path"])
        if not v2path or not os.path.isfile(v2path):
            skipped_no_file += 1
            continue
        if v2path in existing:
            skipped_dup += 1
            continue

        status = "active" if (r["status"] == "ready") else (r["status"] or "active")
        # V1 的 video_url 字段实际是 magnet 链接
        magnet = r["video_url"] if (r["video_url"] or "").startswith("magnet") else r["magnet"]

        try:
            cur2.execute(
                """INSERT INTO movies (
                    file_path,title,title_en,year,poster_url,backdrop_url,rating,
                    genre,country,director,actors,overview,file_size,duration_sec,
                    source,magnet,status,view_count,like_count,is_favorite,tags,
                    has_subtitle,download_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    v2path, r["title"], r["title_en"], r["year"],
                    r["poster"], r["cover_url"], r["rating"],
                    r["genre"], r["country"], r["director"], r["actors"],
                    r["summary"], r["file_size"], r["duration"],
                    r["source"], magnet, status,
                    r["views"] or 0, r["likes"] or 0,
                    1 if r["is_favorite"] else 0, r["tags"],
                    0,  # has_subtitle
                    "none",  # download_status
                ),
            )
            inserted += 1
            existing.add(v2path)
        except Exception as e:
            errors.append((r["title"], str(e)))

    con2.commit()
    print(f"插入: {inserted}")
    print(f"跳过(文件不存在): {skipped_no_file}")
    print(f"跳过(已在V2): {skipped_dup}")
    print(f"错误: {len(errors)}")
    for t, e in errors[:10]:
        print(f"   ERR {t}: {e}")

    total = cur2.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    print(f"\nV2 movies 总数: {total}")
    con2.close()
    con1.close()

if __name__ == "__main__":
    main()
