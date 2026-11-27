"""Giới hạn đăng nhập sai theo cặp (tên đăng nhập, IP) — chống dò mật khẩu mà không khóa tài khoản vĩnh viễn.

Quy tắc: sai `max_failures` lần trong `window_s` giây thì cặp đó bị tạm khóa `lockout_s` giây (429, có Retry-After).
- Chỉ khóa **cặp** tài khoản + IP: người khác (IP khác) vẫn đăng nhập được, kẻ dò từ một IP không khóa được admin ở
  máy khác. Hết thời gian khóa thì tự mở, không cần ai can thiệp, nên admin không bao giờ bị khóa vĩnh viễn.
- Đăng nhập đúng xóa bộ đếm của cặp đó.
- Trong lúc khóa không kiểm mật khẩu (không tốn bcrypt, không cho dò tiếp).

Lưu trong bộ nhớ của tiến trình: portal-api chạy một tiến trình uvicorn nên đủ; khởi động lại thì bộ đếm về 0 (chấp
nhận được cho lab). Tên đăng nhập so khớp không phân biệt hoa thường để không lách bằng "Admin"/"admin".
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field

MAX_KEYS = 10_000  # chặn bộ nhớ khi bị gửi dồn nhiều tên/IP khác nhau


@dataclass
class _Entry:
    failures: deque[float] = field(default_factory=deque)
    locked_until: float = 0.0


@dataclass(frozen=True)
class FailureResult:
    locked: bool          # lần sai này làm cặp bị khóa
    retry_after_s: int    # còn bao lâu thì mở (0 nếu chưa khóa)
    failures: int         # số lần sai trong cửa sổ


class LoginGuard:
    def __init__(self, max_failures: int, window_s: float, lockout_s: float) -> None:
        self.max_failures, self.window_s, self.lockout_s = max_failures, window_s, lockout_s
        self._entries: dict[tuple[str, str], _Entry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(username: str, ip: str | None) -> tuple[str, str]:
        return (username.strip().lower()[:64], ip or "?")

    def retry_after(self, key: tuple[str, str], now: float) -> int:
        """Số giây còn bị khóa (0 = được thử)."""
        with self._lock:
            e = self._entries.get(key)
            if e is None or e.locked_until <= now:
                return 0
            return max(1, int(e.locked_until - now + 0.999))

    def failure(self, key: tuple[str, str], now: float) -> FailureResult:
        with self._lock:
            self._prune(now)
            e = self._entries.setdefault(key, _Entry())
            while e.failures and e.failures[0] <= now - self.window_s:
                e.failures.popleft()
            e.failures.append(now)
            if len(e.failures) >= self.max_failures:
                e.locked_until = now + self.lockout_s
                e.failures.clear()  # hết khóa thì được thử lại đủ max_failures lần
                return FailureResult(True, int(self.lockout_s), self.max_failures)
            return FailureResult(False, 0, len(e.failures))

    def success(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def _prune(self, now: float) -> None:
        if len(self._entries) < MAX_KEYS:
            return
        stale = [k for k, e in self._entries.items()
                 if e.locked_until <= now and (not e.failures or e.failures[-1] <= now - self.window_s)]
        for k in stale:
            del self._entries[k]
        while len(self._entries) >= MAX_KEYS:  # vẫn đầy (đang bị dồn): bỏ mục cũ nhất
            del self._entries[next(iter(self._entries))]
