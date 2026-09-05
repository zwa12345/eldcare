"""数据库 - SQLAlchemy 2.x 同步引擎 + WAL 模式

V2 暂用同步会话（更简单），后续根据需要切 async。
"""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings, get_settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""

    pass


def _make_engine(settings: Settings):
    """构造 SQLite 引擎 + 启用 WAL + 外键"""
    p = Path(settings.db_path).resolve()
    # Windows 路径：url 形式 sqlite:///C:/.../movies.db
    url = f"sqlite:///{p.as_posix()}"

    engine = create_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        """启用 WAL 模式 + 外键"""
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    return engine


_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = _make_engine(settings)
        _SessionLocal = sessionmaker(
            bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False
        )
    return _engine


def get_session_factory():
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db() -> None:
    """创建所有表（首次启动）"""
    # 导入所有模型以注册 metadata
    from app.models import movie, category, watch, search, user, download  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """事务级别的会话（自动 commit / rollback）"""
    factory = get_session_factory()
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI Depends 用的会话生成器（无事务管理，每个端点自己 commit）"""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
