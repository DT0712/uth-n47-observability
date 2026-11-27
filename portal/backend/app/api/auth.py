"""/api/auth/* — đăng nhập, người dùng hiện tại, đăng xuất, đổi mật khẩu (UC01, FR-P01)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_operator
from app.core.errors import ApiError
from app.core.security import DUMMY_HASH, create_token, hash_password, verify_password
from app.db import models as m
from app.schemas.users import LoginRequest, PasswordChange, TokenResponse, User
from app.services import audit
from app.services.login_guard import FailureResult

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _too_many(retry_after_s: int) -> ApiError:
    minutes = max(1, -(-retry_after_s // 60))
    return ApiError(429, "too_many_login_attempts",
                    f"Đăng nhập sai quá nhiều lần. Thử lại sau khoảng {minutes} phút",
                    headers={"Retry-After": str(retry_after_s)})


def _authenticate(db: Session, request: Request, body: LoginRequest,
                  key: tuple[str, str]) -> TokenResponse | FailureResult:
    """Phần đồng bộ (bcrypt, CSDL): chạy trong threadpool để endpoint async không chặn vòng sự kiện."""
    settings, clock, guard = request.app.state.settings, request.app.state.clock, request.app.state.login_guard
    user = db.scalar(select(m.User).where(m.User.username == body.username))
    # Luôn chạy bcrypt (kể cả khi không có user) để thời gian phản hồi không tiết lộ tài khoản có tồn tại
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not (user and ok and user.is_active):
        reason = "no_user" if user is None else ("disabled" if ok else "bad_password")
        audit.record(db, request, "login_failed", user, "user", user.id if user else None,
                     {"username": body.username[:64], "reason": reason})
        result = guard.failure(key, clock.now().timestamp())
        if result.locked:
            audit.record(db, request, "login_locked", user, "user", user.id if user else None,
                         {"username": body.username[:64], "failures": result.failures,
                          "window_s": settings.login_window_s, "lockout_s": result.retry_after_s})
        db.commit()
        return result
    guard.success(key)
    now = clock.now()
    token, expires = create_token(user.id, now, settings.jwt_expire_minutes, settings.jwt_secret)
    user.last_login_at = now
    audit.record(db, request, "login", user, "user", user.id)
    db.commit()
    return TokenResponse(access_token=token, expires_at=expires, user=User.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    settings, clock, guard = request.app.state.settings, request.app.state.clock, request.app.state.login_guard
    key = guard.key(body.username, audit.client_ip(request))
    # Cặp tên + IP đang bị tạm khóa: từ chối ngay, không kiểm mật khẩu
    if wait := guard.retry_after(key, clock.now().timestamp()):
        raise _too_many(wait)
    result = await run_in_threadpool(_authenticate, db, request, body, key)
    if isinstance(result, TokenResponse):
        return result
    if settings.login_failure_delay_s:
        await asyncio.sleep(settings.login_failure_delay_s)  # chờ không giữ luồng xử lý nào
    if result.locked:
        raise _too_many(result.retry_after_s)
    raise ApiError(401, "invalid_credentials", "Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản đã bị khóa",
                   headers={"WWW-Authenticate": "Bearer"})


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
