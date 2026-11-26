"""Thao tác xử lý sự cố của operator (UC06–UC09) và các quy tắc BR-01, BR-02, BR-04.

Mỗi thao tác: khóa dòng sự cố (PostgreSQL: SELECT ... FOR UPDATE), kiểm trạng thái, ghi dòng thời gian (người + thời
điểm, BR-02) và nhật ký thao tác trong cùng transaction.
"""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.db import models as m
from app.schemas.incidents import IncidentSummary
from app.services import audit


def lock(db: Session, incident_id: int) -> m.Incident:
    inc = db.scalar(select(m.Incident).where(m.Incident.id == incident_id).with_for_update())
    if inc is None:
        raise not_found("sự cố")
    return inc


def _not_closed(inc: m.Incident) -> None:
    if inc.status == "closed":
        raise ApiError(409, "incident_closed", "Sự cố đã đóng, không thể thao tác thêm")


def can_close(inc: m.Incident) -> bool:
    """BR-01: đóng được khi chưa đóng và (không còn đợt firing hoặc đã đánh dấu báo giả)."""
    return inc.status != "closed" and (not inc.firing or inc.is_false_positive)


def _log(db: Session, request: Request, inc: m.Incident, user: m.User, type_: str,
         content: str | None) -> m.IncidentEvent:
    now = request.app.state.clock.now()
    event = m.IncidentEvent(incident_id=inc.id, at=now, user_id=user.id, type=type_, content=content)
    db.add(event)
    audit.record(db, request, type_ if type_ != "note" else "incident_note", user, "incident", inc.id,
                 {"content": content} if content else None)
    return event


def acknowledge(db: Session, request: Request, incident_id: int, user: m.User) -> m.Incident:
    inc = lock(db, incident_id)
    if inc.status != "open":
        _not_closed(inc)
        raise ApiError(409, "incident_not_open", "Chỉ xác nhận được sự cố đang ở trạng thái mở")
    inc.status, inc.acknowledged_at, inc.acknowledged_by = "acknowledged", request.app.state.clock.now(), user.id
    _log(db, request, inc, user, "acknowledged", None)
    db.commit()
    return inc


def add_note(db: Session, request: Request, incident_id: int, user: m.User, content: str) -> m.IncidentEvent:
    inc = lock(db, incident_id)
    _not_closed(inc)
    event = _log(db, request, inc, user, "note", content)
    db.commit()
    return event


def mark_false_positive(db: Session, request: Request, incident_id: int, user: m.User, reason: str) -> m.Incident:
    inc = lock(db, incident_id)
    _not_closed(inc)
    inc.is_false_positive, inc.false_positive_reason = True, reason.strip()
    _log(db, request, inc, user, "false_positive", reason.strip())
    db.commit()
    return inc


def close(db: Session, request: Request, incident_id: int, user: m.User, conclusion: str) -> m.Incident:
    inc = lock(db, incident_id)
    _not_closed(inc)
    if not can_close(inc):
        raise ApiError(409, "incident_still_firing",
                       "Không thể đóng sự cố khi còn cảnh báo firing (BR-01). Chờ resolved hoặc đánh dấu báo giả.")
    inc.status, inc.closed_at, inc.closed_by, inc.conclusion = "closed", request.app.state.clock.now(), user.id, conclusion
    _log(db, request, inc, user, "closed", conclusion)
    db.commit()
    return inc


def summaries(db: Session, rows: list[m.Incident]) -> list[IncidentSummary]:
    if not rows:
        return []
    ids = [r.id for r in rows]
    counts = dict(db.execute(select(m.AlertEpisode.incident_id, func.count()).where(
        m.AlertEpisode.incident_id.in_(ids)).group_by(m.AlertEpisode.incident_id)).all())
    latest: dict[int, str | None] = {}
    for ep in db.scalars(select(m.AlertEpisode).where(m.AlertEpisode.incident_id.in_(ids))
                         .order_by(m.AlertEpisode.starts_at)):
        latest[ep.incident_id] = ep.annotations.get("summary")
    return [IncidentSummary(id=r.id, alertname=r.alertname, instance=r.instance, host=r.host, service=r.service,
                            severity=r.severity, status=r.status, firing=r.firing, is_false_positive=r.is_false_positive,
                            episode_count=counts.get(r.id, 0), summary=latest.get(r.id), opened_at=r.opened_at,
                            acknowledged_at=r.acknowledged_at, closed_at=r.closed_at) for r in rows]
