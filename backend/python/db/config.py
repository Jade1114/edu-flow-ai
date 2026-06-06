"""Database configuration and connection helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import pymysql
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: pymysql. Run `cd ml && python3 -m venv .venv "
        "&& source .venv/bin/activate && pip install -r requirements.txt` first."
    ) from exc

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT_DIR.parent

DEFAULT_DB_URL = (
    "jdbc:mysql://localhost:3306/edu_flow_ai?useUnicode=true&characterEncoding=utf8"
    "&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&useSSL=false"
)
DEFAULT_DB_USERNAME = "root"
DEFAULT_DB_PASSWORD = ""


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    charset: str = "utf8mb4"


def load_env_files() -> None:
    """Load DB settings from project-level .env files without overriding real env vars."""
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_jdbc_mysql_url(url: str) -> tuple[str, int, str, dict[str, list[str]]]:
    if url.startswith("jdbc:"):
        url = url[len("jdbc:") :]
    parsed = urlparse(url)
    if parsed.scheme != "mysql":
        raise ValueError(f"Only jdbc:mysql URLs are supported, got: {parsed.scheme}")
    database = parsed.path.lstrip("/")
    if not database:
        raise ValueError("Database name is missing from DB_URL")
    return parsed.hostname or "localhost", parsed.port or 3306, database, parse_qs(parsed.query)


def load_db_config() -> DbConfig:
    load_env_files()
    db_url = os.getenv("DB_URL", DEFAULT_DB_URL)
    host, port, database, query = parse_jdbc_mysql_url(db_url)
    charset = query.get("characterEncoding", ["utf8mb4"])[0]
    if charset.lower() == "utf8":
        charset = "utf8mb4"
    return DbConfig(
        host=host,
        port=port,
        database=database,
        user=os.getenv("DB_USERNAME", DEFAULT_DB_USERNAME),
        password=os.getenv("DB_PASSWORD", DEFAULT_DB_PASSWORD),
        charset=charset,
    )


def connect(config: DbConfig):
    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        charset=config.charset,
        cursorclass=pymysql.cursors.DictCursor,
    )
