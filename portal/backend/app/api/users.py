"""/api/users — quản lý người dùng, chỉ admin (UC14, FR-P16)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.errors import ApiError, not_found
from app.core.security import hash_password
from app.db import models as m
from app.schemas.common import Page, PageParams
from app.schemas.users import User, UserCreate, UserUpdate
from app.services import audit
from app.services.users import check_update_allowed

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=Page[User])
def list_users(p: PageParams = Depends(), _: m.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    items, total = p.apply(db, select(m.User).order_by(m.User.username))
    return {"items": items, "total": total, "page": p.page, "page_size": p.page_size}


@router.post("", response_model=User, status_code=201)
def create_user(body: UserCreate, request: Request, actor: m.User = Depends(require_admin),
                db: Session = Depends(get_db)) -> m.User:
    if db.scalar(select(m.User.id).where(m.User.username == body.username)):
        raise ApiError(409, "duplicate", f"Tên đăng nhập '{body.username}' đã tồn tại")
    user = m.User(username=body.username, role=body.role, is_active=True, created_at=request.app.state.clock.now(),
                  password_hash=hash_password(body.password, request.app.state.settings.bcrypt_rounds))
    db.add(user)
    db.flush()
    audit.record(db, request, "create", actor, "user", user.id, {"username": user.username, "role": user.role})
    db.commit()
    return user


@router.patch("/{user_id}", response_model=User)
def update_user(user_id: int, body: UserUpdate, request: Request, actor: m.User = Depends(require_admin),
                db: Session = Depends(get_db)) -> m.User:
    target = db.get(m.User, user_id)
    if target is None:
        raise not_found("người dùng")
    actor = db.get(m.User, actor.id)
    check_update_allowed(db, actor, target, body.role, body.is_active)
    changes: dict = {}
    if body.role is not None and body.role != target.role:
        changes["role"] = [target.role, body.role]
        target.role = body.role
    if body.is_active is not None and body.is_active != target.is_active:
        changes["is_active"] = [target.is_active, body.is_active]
        target.is_active = body.is_active
    if body.password is not None:
        target.password_hash = hash_password(body.password, request.app.state.settings.bcrypt_rounds)
        changes["password"] = "đặt lại"  # không bao giờ ghi mật khẩu vào nhật ký
    if changes:
        audit.record(db, request, "update", actor, "user", target.id, changes)
    db.commit()
    return target
