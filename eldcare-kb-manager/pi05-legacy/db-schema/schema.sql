-- table: categories
CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            icon TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

-- table: movies
CREATE TABLE movies (
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
        , magnet TEXT);

-- table: search_history
CREATE TABLE search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

-- table: sqlite_sequence
CREATE TABLE sqlite_sequence(name,seq);

-- table: watch_history
CREATE TABLE watch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER,
            position INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (movie_id) REFERENCES movies(id)
        );
