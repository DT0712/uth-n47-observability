"""Nạp runbook từ runbooks/*.md (FR-P11). Nguồn sự thật là file trong git; CSDL chỉ là bản sao để tra cứu nhanh.

Mỗi file: front matter YAML (alertname, title, severity, category, status) + nội dung Markdown.
Nạp lúc khởi động và khi admin gọi POST /api/runbooks/reload. File không đổi (cùng sha256) thì bỏ qua;
file đã bị xóa khỏi thư mục thì xóa khỏi CSDL.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.db import models as m

log = logging.getLogger(__name__)

# Khi chạy từ repo trên Windows: <repo>/portal/backend/app/services/ -> <repo>/runbooks. Trong container code ở /app/app/...
# (không đủ 5 cấp thư mục) nên rơi về "/", và thư mục cấu hình /runbooks được dùng trước.
_PARENTS = Path(__file__).resolve().parents
REPO_RUNBOOKS = (_PARENTS[4] if len(_PARENTS) > 4 else _PARENTS[-1]) / "runbooks"
FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.S)
ALERTNAME = re.compile(r"^[A-Za-z0-9_]{1,128}$")


@dataclass
class LoadResult:
    loaded: int = 0      # số runbook hợp lệ trong thư mục
    updated: int = 0     # số runbook mới hoặc đã đổi nội dung
    removed: int = 0     # số runbook bị xóa vì file không còn
    errors: list[str] = field(default_factory=list)


def resolve_dir(configured: str) -> Path:
    """Thư mục cấu hình (container: /runbooks); không có thì dùng runbooks/ của repo (chạy trên Windows)."""
    p = Path(configured)
    return p if p.is_dir() else REPO_RUNBOOKS


def parse(path: Path) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    match = FRONT_MATTER.match(text)
    if not match:
        raise ValueError("thiếu front matter (--- ... ---)")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("front matter không phải dạng khóa: giá trị")
    alertname = str(meta.get("alertname", ""))
    if not ALERTNAME.match(alertname):
        raise ValueError(f"alertname không hợp lệ: {alertname!r}")
    if alertname != path.stem:
        raise ValueError(f"alertname {alertname!r} khác tên file")
    status = meta.get("status", "draft")
    return {
        "alertname": alertname,
        "title": str(meta.get("title") or alertname)[:256],
        "severity": (str(meta["severity"]) if meta.get("severity") else None),
        "category": (str(meta["category"]) if meta.get("category") else None),
        "status": status if status in ("draft", "reviewed") else "draft",
        "body_md": match.group(2).lstrip("\r\n"),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
    }


def load(db: Session, directory: Path, clock: Clock) -> LoadResult:
    result = LoadResult()
    if not directory.is_dir():
        result.errors.append(f"Không thấy thư mục runbook: {directory}")
        return result
    existing = {r.alertname: r for r in db.scalars(select(m.Runbook))}
    seen: set[str] = set()
    for path in sorted(directory.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        try:
            data = parse(path)
        except (ValueError, UnicodeDecodeError, yaml.YAMLError) as e:
            result.errors.append(f"{path.name}: {e}")
            continue
        seen.add(data["alertname"])
        result.loaded += 1
        row = existing.get(data["alertname"])
        if row is not None and row.source_sha256 == data["source_sha256"]:
            continue
        if row is None:
            row = m.Runbook(alertname=data["alertname"])
            db.add(row)
        for key, value in data.items():
            setattr(row, key, value)
        row.source_path = f"runbooks/{path.name}"
        row.loaded_at = clock.now()
        result.updated += 1
    for name, row in existing.items():
        if name not in seen:
            db.delete(row)
            result.removed += 1
    db.commit()
    for err in result.errors:
        log.warning("Runbook lỗi: %s", err)
    return result
