"""Đọc thời gian ISO-8601 của Alertmanager (nano giây, "Z", mốc 0001-01-01 = chưa kết thúc)."""

from __future__ import annotations

from datetime import datetime, timezone


def parse_am_time(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip().replace("Z", "+00:00")
    if "." in v:  # Python chỉ nhận tối đa 6 chữ số thập phân
        head, rest = v.split(".", 1)
        digits = "".join(c for c in rest if c.isdigit())
        tz = rest[len(digits):]
        v = f"{head}.{digits[:6].ljust(6, '0')}{tz}"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt.year < 1970:
        return None
    return dt.astimezone(timezone.utc)
