"""Dependency dùng chung cho các router: phiên CSDL, đồng hồ, cấu hình."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings
