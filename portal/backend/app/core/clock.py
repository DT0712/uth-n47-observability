"""Đồng hồ của backend. Mọi mốc thời gian lấy qua đây để test thay được bằng đồng hồ giả (FakeClock)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class Clock:
    def now(self) -> datetime:
        """Thời điểm hiện tại, UTC, có múi giờ, độ chính xác mili-giây."""
        t = datetime.now(timezone.utc)
        return t.replace(microsecond=t.microsecond // 1000 * 1000)


class FakeClock(Clock):
    def __init__(self, start: datetime | None = None) -> None:
        self._t = start or datetime(2026, 11, 26, 7, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._t

    def advance(self, seconds: float) -> datetime:
        self._t += timedelta(seconds=seconds)
        return self._t
