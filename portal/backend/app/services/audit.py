"""Nhật ký thao tác (FR-P17): mọi thao tác thay đổi dữ liệu, đăng nhập, chạy/dừng kịch bản lỗi.

Ghi trong cùng transaction với thao tác: thao tác thất bại (rollback) thì không có dòng audit sai.
Riêng đăng nhập thất bại được ghi và commit riêng (không có thao tác nào khác để đi kèm).
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.db import models as m


def client_ip(request: Request | None) -> str | None:
    return request.client.host if request is not None and request.client else None


def record(db: Session, request: Request, action: str, user: m.User | None = None,
           object_type: str | None = None, object_id: Any = None, detail: dict[str, Any] | None = None) -> m.AuditLog:
    entry = m.AuditLog(at=request.app.state.clock.now(), user_id=user.id if user else None,
                       action=action, object_type=object_type, object_id=None if object_id is None else str(object_id),
                       detail=detail, client_ip=client_ip(request))
    db.add(entry)
    return entry
