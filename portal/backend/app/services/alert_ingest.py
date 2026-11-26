"""Nhận webhook Alertmanager -> đợt cảnh báo -> sự cố (FR-P08, BR-03, BR-08, NFR-06).

Thứ tự trong một transaction (docs/02-thiet-ke/so-do-tuan-tu.md, luồng 2):
  1. Lưu payload thô (webhook_receipts). Payload trùng hoàn toàn (hash) -> bỏ qua, duplicate=true.
  2. Mỗi alert:
     - firing, đợt mới (fingerprint, startsAt chưa có)  -> tạo đợt; gắn vào sự cố chưa đóng cùng (alertname, instance),
       không có thì tạo sự cố mới; gọi các hook (phần 7: khớp với lần chạy kịch bản lỗi)
     - firing, đợt đã có (Alertmanager gửi lại theo repeat_interval) -> chỉ cập nhật last_received_at
     - resolved -> đợt resolved; sự cố còn đợt nào firing không
     - resolved mà chưa từng thấy firing (portal tắt lúc đó) -> tạo đợt đã resolved, đánh dấu "nhận muộn"
  Lỗi ở một alert không làm hỏng các alert khác (savepoint), được đếm vào errors.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.timeutil import parse_am_time
from app.db import models as m
from app.schemas.incidents import AlertmanagerWebhook, AMAlert

log = logging.getLogger(__name__)

SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}
# Hook nhận (db, đợt firing mới); phần 7 đăng ký hàm khớp với lần chạy kịch bản lỗi
FiringHook = Callable[[Session, m.AlertEpisode], None]


@dataclass
class IngestResult:
    receipt_id: int | None = None
    duplicate: bool = False
    episodes_created: int = 0
    episodes_updated: int = 0
    incidents_created: int = 0
    errors: int = 0
    new_firing: list[int] = field(default_factory=list)


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _ends_at(alert: AMAlert) -> datetime | None:
    return parse_am_time(alert.endsAt)


def _severity(labels: dict[str, str]) -> str:
    s = labels.get("severity", "warning")
    return s if s in SEVERITY_RANK else "warning"


def _event(db: Session, inc: m.Incident, now: datetime, type_: str, content: str | None = None,
           data: dict | None = None) -> None:
    db.add(m.IncidentEvent(incident_id=inc.id, at=now, user_id=None, type=type_, content=content, data=data))


def _attach(db: Session, ep: m.AlertEpisode, now: datetime, result: IngestResult) -> m.Incident:
    """BR-08: gắn đợt vào sự cố chưa đóng cùng (alertname, instance), không có thì tạo mới."""
    key = (m.Incident.alertname == ep.alertname, m.Incident.instance == ep.instance, m.Incident.status != "closed")
    inc = db.scalar(select(m.Incident).where(*key))
    if inc is None:
        try:
            with db.begin_nested():  # hai webhook cùng lúc: unique index chặn, thử đọc lại
                inc = m.Incident(alertname=ep.alertname, instance=ep.instance, host=ep.host, service=ep.service,
                                 severity=ep.severity, status="open", firing=ep.status == "firing",
                                 opened_at=now)
                db.add(inc)
                db.flush()
            result.incidents_created += 1
            _event(db, inc, now, "opened", ep.annotations.get("summary"))
        except IntegrityError:
            inc = db.scalar(select(m.Incident).where(*key))
            if inc is None:
                raise
    if SEVERITY_RANK[ep.severity] > SEVERITY_RANK.get(inc.severity, 0):
        inc.severity = ep.severity
    ep.incident_id = inc.id
    if ep.status == "firing":
        inc.firing = True
        _event(db, inc, now, "episode_firing", ep.annotations.get("summary"), {"episode_id": ep.id})
    return inc


def _refresh_firing(db: Session, inc: m.Incident) -> None:
    db.flush()
    inc.firing = db.scalar(select(m.AlertEpisode.id).where(m.AlertEpisode.incident_id == inc.id,
                                                            m.AlertEpisode.status == "firing").limit(1)) is not None


def _ingest_alert(db: Session, a: AMAlert, receipt: m.WebhookReceipt, now: datetime, result: IngestResult) -> None:
    starts = parse_am_time(a.startsAt)
    if starts is None:
        raise ValueError(f"startsAt không hợp lệ: {a.startsAt!r}")
    ep = db.scalar(select(m.AlertEpisode).where(m.AlertEpisode.fingerprint == a.fingerprint,
                                                m.AlertEpisode.starts_at == starts))
    if ep is not None:
        ep.last_received_at, ep.last_receipt_id = now, receipt.id
        if a.status == "resolved" and ep.status == "firing":
            ep.status, ep.ends_at, ep.resolved_received_at = "resolved", _ends_at(a), now
            inc = db.get(m.Incident, ep.incident_id) if ep.incident_id else None
            if inc is not None:
                _refresh_firing(db, inc)
                _event(db, inc, now, "episode_resolved", None, {"episode_id": ep.id})
        result.episodes_updated += 1
        return

    labels = dict(a.labels)
    ep = m.AlertEpisode(
        fingerprint=a.fingerprint, starts_at=starts, ends_at=_ends_at(a) if a.status == "resolved" else None,
        status=a.status, alertname=labels.get("alertname", "(không tên)")[:128], instance=labels.get("instance", "")[:256],
        host=labels.get("host"), service=labels.get("service"), severity=_severity(labels), labels=labels,
        annotations=dict(a.annotations), first_received_at=now, last_received_at=now, last_receipt_id=receipt.id,
        resolved_received_at=now if a.status == "resolved" else None)
    db.add(ep)
    db.flush()
    inc = _attach(db, ep, now, result)
    if a.status == "resolved":  # chưa từng nhận firing của đợt này
        _event(db, inc, now, "episode_resolved", "Nhận resolved khi chưa ghi nhận firing (portal có thể đã tắt)",
               {"episode_id": ep.id, "late": True})
        _refresh_firing(db, inc)
    else:
        result.new_firing.append(ep.id)
    result.episodes_created += 1


def ingest(db: Session, payload: dict, clock: Clock, hooks: list[FiringHook] | None = None) -> IngestResult:
    body = AlertmanagerWebhook.model_validate(payload)
    now = clock.now()  # T1: thời điểm backend nhận (đồng hồ monitor)
    result = IngestResult()
    receipt = m.WebhookReceipt(received_at=now, payload_sha256=payload_hash(payload), group_key=body.groupKey,
                               status=body.status, alert_count=len(body.alerts), payload=payload)
    try:
        with db.begin_nested():
            db.add(receipt)
            db.flush()
    except IntegrityError:
        db.rollback()
        return IngestResult(duplicate=True)
    result.receipt_id = receipt.id
    for a in body.alerts:
        try:
            with db.begin_nested():
                _ingest_alert(db, a, receipt, now, result)
        except Exception:  # một alert lỗi không làm mất cả payload (đã lưu thô, xử lý lại được)
            log.exception("Không xử lý được alert %s", a.fingerprint)
            result.errors += 1
    for ep_id in result.new_firing:
        ep = db.get(m.AlertEpisode, ep_id)
        for hook in hooks or []:
            try:
                with db.begin_nested():
                    hook(db, ep)
            except Exception:
                log.exception("Hook lỗi với đợt %s", ep_id)
    db.commit()
    return result
