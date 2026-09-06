"""配置层 - Pydantic Settings 从 .env / 环境变量加载

所有变量必须以 ELDCARE_ 前缀（model_config.env_prefix 设置）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_BASE_DIR = Path(__file__).resolve().parents[2]  # v2/（项目根）


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ELDCARE_",
        env_file=_BASE_DIR / ".env",  # 相对项目根加载，避免依赖启动 CWD
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 服务
    port: int = 8090
    host: str = "0.0.0.0"

    # 节点角色
    node_role: Literal["master", "slave"] = "master"
    instance_id: str = Field(default="local-dev", description="实例唯一标识")

    # 路径
    data_dir: Path = Path("./data")
    movies_dir: Path = Path("./data/movies")
    thumbs_dir: Path = Path("./data/thumbs")
    subtitles_dir: Path = Path("./data/subtitles")
    downloads_dir: Path = Path("./data/downloads")
    log_dir: Path = Path("./data/logs")
    db_path: Path = Path("./data/movies.db")

    # 主备同步
    peer_url: str = ""
    peer_token: str = ""
    sync_interval_seconds: int = 1800

    # TMDB
    tmdb_api_key: str = ""
    tmdb_lang: str = "zh-CN"

    # aria2
    aria2_rpc_url: str = "http://127.0.0.1:6800/jsonrpc"
    aria2_secret: str = ""

    # 日志
    log_level: str = "INFO"

    # 鉴权
    jwt_secret: str = "change-me-in-production"
    jwt_ttl_hours: int = 720

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    def model_post_init(self, __context) -> None:
        """初始化路径对象：相对路径相对项目根解析，并自动 mkdir

        规则：
        - 仅对 *目录* 类字段做 mkdir
        - db_path 是文件路径，只确保其父目录存在
        """
        base = _BASE_DIR
        dir_fields = (
            "data_dir", "movies_dir", "thumbs_dir", "subtitles_dir",
            "downloads_dir", "log_dir",
        )
        for k in dir_fields:
            v = getattr(self, k)
            if not v.is_absolute():
                v = base / v
                object.__setattr__(self, k, v.resolve())
            v.mkdir(parents=True, exist_ok=True)

        # db_path 只确保父目录存在，不要把 db_path 本身 mkdir
        if not self.db_path.is_absolute():
            self.db_path = (base / self.db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def is_master(self) -> bool:
        return self.node_role == "master"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"


_settings: Settings | None = None


def get_settings() -> Settings:
    """FastAPI Depends 用的依赖函数"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
