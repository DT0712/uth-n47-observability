"""Băm mật khẩu (bcrypt) và JWT (HS256) — NFR-02.

Hạn của token được kiểm bằng đồng hồ của app (Clock), không bằng giờ hệ thống, để test tua thời gian được.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import bcrypt
import jwt

ALGORITHM = "HS256"
_BCRYPT_MAX_BYTES = 72  # bcrypt chỉ dùng 72 byte đầu; schema giới hạn mật khẩu 128 ký tự


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode()[:_BCRYPT_MAX_BYTES], bcrypt.gensalt(rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:_BCRYPT_MAX_BYTES], password_hash.encode())
    except ValueError:
        return False


# Băm sẵn một mật khẩu giả: khi username không tồn tại vẫn tốn thời gian như khi sai mật khẩu,
# để không đoán được tài khoản nào có thật qua thời gian phản hồi.
DUMMY_HASH = hash_password("khong-phai-mat-khau-that", rounds=12)


@dataclass(frozen=True)
class TokenData:
    user_id: int
    expires_at: datetime


class TokenError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code  # token_expired | not_authenticated


def create_token(user_id: int, now: datetime, minutes: int, secret: str) -> tuple[str, datetime]:
    expires = now + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int(expires.timestamp())}
    return jwt.encode(payload, secret, algorithm=ALGORITHM), expires


def decode_token(token: str, now: datetime, secret: str) -> TokenData:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM], options={"verify_exp": False,
                                                                             "require": ["sub", "exp"]})
        user_id, exp = int(payload["sub"]), int(payload["exp"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise TokenError("not_authenticated") from None
    if now.timestamp() >= exp:
        raise TokenError("token_expired")
    return TokenData(user_id, datetime.fromtimestamp(exp, tz=now.tzinfo))
