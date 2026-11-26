"""Nghiệp vụ người dùng: tạo admin đầu tiên, tạo/sửa tài khoản với các quy tắc an toàn."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import hash_password
from app.db import models as m

log = logging.getLogger(__name__)


def ensure_bootstrap_admin(db: Session, settings: Settings, clock: Clock) -> m.User | None:
    """Bảng users rỗng thì tạo admin từ PORTAL_BOOTSTRAP_ADMIN_* (chỉ một lần, lúc khởi động)."""
    try:
        if db.scalar(select(func.count()).select_from(m.User)):
            return None
    except (OperationalError, ProgrammingError):
        log.warning("Chưa có bảng users — chạy migration trước: python -m app.db.migrate")
        db.rollback()
        return None
    admin = m.User(username=settings.bootstrap_admin_user,
                   password_hash=hash_password(settings.bootstrap_admin_password, settings.bcrypt_rounds),
                   role="admin", is_active=True, created_at=clock.now())
    db.add(admin)
    db.commit()
    log.info("Đã tạo admin đầu tiên: %s", admin.username)
    return admin


def active_admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(m.User).where(m.User.role == "admin", m.User.is_active)) or 0


def check_update_allowed(db: Session, actor: m.User, target: m.User, role: str | None, is_active: bool | None) -> None:
    """Không tự khóa/tự hạ quyền; không để hệ thống còn 0 admin đang hoạt động."""
    demote = role is not None and role != "admin" and target.role == "admin"
    disable = is_active is False and target.is_active
    if not (demote or disable):
        return
    if target.id == actor.id:
        raise ApiError(409, "self_modification", "Không thể tự khóa hoặc tự hạ vai trò của chính mình")
    if target.role == "admin" and target.is_active and active_admin_count(db) <= 1:
        raise ApiError(409, "last_admin", "Phải còn ít nhất một admin đang hoạt động")
