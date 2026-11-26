"""Chạy migration Alembic từ mã Python (test và khi khởi động container).

  python -m app.db.migrate          # = alembic upgrade head với DATABASE_URL hiện tại
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade(engine: Engine, revision: str = "head") -> None:
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, revision)


def downgrade(engine: Engine, revision: str = "base") -> None:
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, revision)


if __name__ == "__main__":
    from app.core.config import Settings
    from app.db.base import make_engine

    url = Settings().database_url
    upgrade(make_engine(url))
    print(f"Đã nâng CSDL lên phiên bản mới nhất: {url}")
