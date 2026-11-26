"""/api/audit — xem nhật ký thao tác, chỉ admin (FR-P17)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.db import models as m
from app.schemas.common import Page, PageParams
from app.schemas.users import AuditEntry

router = APIRouter(prefix="/api/audit", tags=["system"])


@router.get("", response_model=Page[AuditEntry])
def list_audit(user_id: int | None = None, action: str | None = None, from_: datetime | None = Query(None, alias="from"),
               to: datetime | None = None, p: PageParams = Depends(), _: m.User = Depends(require_admin),
               db: Session = Depends(get_db)) -> dict:
    stmt = select(m.AuditLog).order_by(m.AuditLog.at.desc(), m.AuditLog.id.desc())
    if user_id is not None:
        stmt = stmt.where(m.AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(m.AuditLog.action == action)
    if from_:
        stmt = stmt.where(m.AuditLog.at >= from_)
    if to:
        stmt = stmt.where(m.AuditLog.at < to)
    rows, total = p.apply(db, stmt)
    names = dict(db.execute(select(m.User.id, m.User.username).where(
        m.User.id.in_({r.user_id for r in rows if r.user_id}))).all()) if rows else {}
    items = [AuditEntry(id=r.id, at=r.at, user=names.get(r.user_id), action=r.action, object_type=r.object_type,
                        object_id=r.object_id, detail=r.detail, client_ip=r.client_ip) for r in rows]
    return {"items": items, "total": total, "page": p.page, "page_size": p.page_size}
