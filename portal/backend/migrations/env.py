"""Môi trường Alembic: dùng metadata của app.db.models và URL từ DATABASE_URL (hoặc -x url=...)."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app.core.config import Settings
from app.db import models  # noqa: F401  (nạp mọi bảng vào metadata)
from app.db.base import Base, make_engine

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return context.get_x_argument(as_dictionary=True).get("url") or config.attributes.get("url") or Settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is None:
        with make_engine(_url()).connect() as conn:
            _run(conn)
    else:
        _run(connection)


def _render_item(type_, obj, autogen_context):
    """Migration không phụ thuộc mã app: UTCDateTime ghi thành sa.DateTime(timezone=True)."""
    if type_ == "type" and obj.__class__.__name__ == "UTCDateTime":
        return "sa.DateTime(timezone=True)"
    return False


def _run(conn) -> None:
    # render_as_batch: SQLite không ALTER được nhiều thứ, Alembic tạo lại bảng thay thế
    context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True, compare_type=True,
                      render_item=_render_item)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
