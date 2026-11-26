"""Dependency dùng chung: phiên CSDL, đồng hồ, cấu hình, người dùng hiện tại và kiểm vai trò (FR-P02, NFR-03).

Mỗi endpoint khai báo vai trò tối thiểu bằng `Depends(require_operator)` hoặc `Depends(require_admin)`, đúng với
`x-min-role` trong openapi.yaml. Vai trò và trạng thái khóa đọc lại từ CSDL ở MỖI request, nên khóa tài khoản hay hạ
vai trò có hiệu lực ngay dù JWT còn hạn.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import TokenError, decode_token
from app.db import models as m

_MESSAGES = {
    "not_authenticated": "Chưa đăng nhập hoặc phiên không hợp lệ",
    "token_expired": "Phiên đăng nhập đã hết hạn, hãy đăng nhập lại",
    "account_disabled": "Tài khoản đã bị khóa",
}
ROLE_RANK = {"operator": 1, "admin": 2}


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def unauthorized(code: str) -> ApiError:
    return ApiError(401, code, _MESSAGES[code], headers={"WWW-Authenticate": "Bearer"})


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> m.User:
    token = bearer_token(request)
    if token is None:
        raise unauthorized("not_authenticated")
    settings: Settings = request.app.state.settings
    try:
        data = decode_token(token, request.app.state.clock.now(), settings.jwt_secret)
    except TokenError as e:
        raise unauthorized(e.code) from None
    user = db.get(m.User, data.user_id)
    if user is None:
        raise unauthorized("not_authenticated")
    if not user.is_active:
        raise unauthorized("account_disabled")
    return user


def _require(min_role: str):
    def checker(user: m.User = Depends(get_current_user)) -> m.User:
        if ROLE_RANK.get(user.role, 0) < ROLE_RANK[min_role]:
            raise ApiError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này")
        return user

    checker.__name__ = f"require_{min_role}"
    return checker


require_operator = _require("operator")
require_admin = _require("admin")
