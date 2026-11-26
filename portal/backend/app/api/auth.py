"""/api/auth/* — đăng nhập, người dùng hiện tại, đăng xuất, đổi mật khẩu (UC01, FR-P01)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_operator
from app.core.errors import ApiError
from app.core.security import DUMMY_HASH, create_token, hash_password, verify_password
from app.db import models as m
from app.schemas.users import LoginRequest, PasswordChange, TokenResponse, User
from app.services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    settings, clock = request.app.state.settings, request.app.state.clock
    user = db.scalar(select(m.User).where(m.User.username == body.username))
    # Luôn chạy bcrypt (kể cả khi không có user) để thời gian phản hồi không tiết lộ tài khoản có tồn tại
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not (user and ok and user.is_active):
        reason = "no_user" if user is None else ("disabled" if ok else "bad_password")
        audit.record(db, request, "login_failed", user, "user", user.id if user else None,
                     {"username": body.username[:64], "reason": reason})
        db.commit()
        if settings.login_failure_delay_s:
            time.sleep(settings.login_failure_delay_s)
        raise ApiError(401, "invalid_credentials", "Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản đã bị khóa",
                       headers={"WWW-Authenticate": "Bearer"})
    now = clock.now()
    token, expires = create_token(user.id, now, settings.jwt_expire_minutes, settings.jwt_secret)
    user.last_login_at = now
    audit.record(db, request, "login", user, "user", user.id)
    db.commit()
    return TokenResponse(access_token=token, expires_at=expires, user=User.model_validate(user))


@router.get("/me", response_model=User)
def me(user: m.User = Depends(require_operator)) -> m.User:
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, user: m.User = Depends(require_operator), db: Session = Depends(get_db)) -> Response:
    # JWT không thu hồi được; client tự xóa token. Ở đây chỉ ghi nhật ký.
    audit.record(db, request, "logout", user, "user", user.id)
    db.commit()
    return Response(status_code=204)


@router.post("/password", status_code=204)
def change_password(body: PasswordChange, request: Request, user: m.User = Depends(require_operator),
                    db: Session = Depends(get_db)) -> Response:
    if not verify_password(body.current_password, user.password_hash):
        # 422 thay vì 401: sai mật khẩu cũ không có nghĩa là phiên hết hạn (client không bị đăng xuất)
        raise ApiError(422, "validation_error", "Dữ liệu không hợp lệ",
                       [{"field": "current_password", "message": "Mật khẩu hiện tại không đúng", "type": "wrong_password"}])
    user = db.merge(user)
    user.password_hash = hash_password(body.new_password, request.app.state.settings.bcrypt_rounds)
    audit.record(db, request, "password_change", user, "user", user.id)
    db.commit()
    return Response(status_code=204)
