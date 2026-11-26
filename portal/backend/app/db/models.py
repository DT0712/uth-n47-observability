"""Mô hình dữ liệu theo docs/02-thiet-ke/erd.md (11 bảng).

Giá trị liệt kê (vai trò, trạng thái...) lưu dạng chuỗi kèm CHECK để migration đơn giản trên cả PostgreSQL và SQLite.
Các quy tắc nghiệp vụ quan trọng có ràng buộc CSDL làm lớp chặn cuối (service vẫn kiểm trước để trả lỗi rõ):
  BR-01  không đóng sự cố khi còn firing, trừ báo giả           -> ck_incidents_close_requires_not_firing
  BR-03  đợt cảnh báo định danh bằng (fingerprint, starts_at)   -> uq_alert_episodes_fingerprint_starts_at
  BR-04  báo giả phải có lý do                                  -> ck_incidents_false_positive_reason
  BR-06  mỗi VM tối đa một lần chạy kịch bản đang hoạt động     -> ux_fault_runs_active_host (unique có điều kiện)
  BR-08  mỗi (alertname, instance) tối đa một sự cố chưa đóng   -> ux_incidents_open_key (unique có điều kiện)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime

ROLES = ("admin", "operator")
SEVERITIES = ("critical", "warning", "info")
ALERT_STATUSES = ("firing", "resolved")
INCIDENT_STATUSES = ("open", "acknowledged", "closed")
INCIDENT_EVENT_TYPES = ("opened", "episode_firing", "episode_resolved", "acknowledged", "note", "false_positive", "closed")
SERVICE_KINDS = ("web", "app", "database", "other")
SCENARIOS = ("cpu", "memory", "disk", "service-stop", "latency", "errors")
FAULT_RUN_STATUSES = ("pending", "running", "recovering", "completed", "failed", "cancelled")
FAULT_RUN_ACTIVE = ("pending", "running", "recovering")
MATCH_ROLES = ("root", "expected", "extra", "unrelated")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(_in("role", ROLES), name="role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Host(Base):
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    address: Mapped[str | None] = mapped_column(String(64))
    prom_instance: Mapped[str] = mapped_column(String(128))
    grafana_dashboard_uid: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    services: Mapped[list[Service]] = relationship(back_populates="host", cascade="all, delete-orphan",
                                                   order_by="Service.name")


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("host_id", "name"),
        CheckConstraint(_in("kind", SERVICE_KINDS), name="kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(16))
    prom_labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    probe_instance: Mapped[str | None] = mapped_column(String(128))
    grafana_dashboard_uid: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    host: Mapped[Host] = relationship(back_populates="services")


class WebhookReceipt(Base):
    __tablename__ = "webhook_receipts"
    __table_args__ = (CheckConstraint(_in("status", ALERT_STATUSES), name="status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime)
    payload_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    group_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    alert_count: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class AlertEpisode(Base):
    __tablename__ = "alert_episodes"
    __table_args__ = (
        UniqueConstraint("fingerprint", "starts_at"),
        CheckConstraint(_in("status", ALERT_STATUSES), name="status"),
        Index("ix_alert_episodes_host_received", "host", "first_received_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(16))
    alertname: Mapped[str] = mapped_column(String(128))
    instance: Mapped[str] = mapped_column(String(256), default="")
    host: Mapped[str | None] = mapped_column(String(64))
    service: Mapped[str | None] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), default="warning")
    labels: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    annotations: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    first_received_at: Mapped[datetime] = mapped_column(UTCDateTime)
    resolved_received_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_received_at: Mapped[datetime] = mapped_column(UTCDateTime)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"))
    last_receipt_id: Mapped[int | None] = mapped_column(ForeignKey("webhook_receipts.id"))

    incident: Mapped[Incident | None] = relationship(back_populates="episodes")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(_in("status", INCIDENT_STATUSES), name="status"),
        CheckConstraint(_in("severity", SEVERITIES), name="severity"),
        CheckConstraint("status <> 'closed' OR firing = false OR is_false_positive = true",
                        name="close_requires_not_firing"),
        CheckConstraint("is_false_positive = false OR length(false_positive_reason) > 0",
                        name="false_positive_reason"),
        Index("ux_incidents_open_key", "alertname", "instance", unique=True,
              sqlite_where=text("status <> 'closed'"), postgresql_where=text("status <> 'closed'")),
        Index("ix_incidents_status_opened", "status", "opened_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alertname: Mapped[str] = mapped_column(String(128))
    instance: Mapped[str] = mapped_column(String(256), default="")
    host: Mapped[str | None] = mapped_column(String(64))
    service: Mapped[str | None] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="open")
    firing: Mapped[bool] = mapped_column(Boolean, default=True)
    is_false_positive: Mapped[bool] = mapped_column(Boolean, default=False)
    false_positive_reason: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    episodes: Mapped[list[AlertEpisode]] = relationship(back_populates="incident", order_by="AlertEpisode.starts_at")
    events: Mapped[list[IncidentEvent]] = relationship(back_populates="incident", order_by="IncidentEvent.id",
                                                       cascade="all, delete-orphan")


class IncidentEvent(Base):
    __tablename__ = "incident_events"
    __table_args__ = (CheckConstraint(_in("type", INCIDENT_EVENT_TYPES), name="type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(32))
    content: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    incident: Mapped[Incident] = relationship(back_populates="events")


class Runbook(Base):
    __tablename__ = "runbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alertname: Mapped[str] = mapped_column(String(128), unique=True)
    title: Mapped[str] = mapped_column(String(256))
    severity: Mapped[str | None] = mapped_column(String(16))
    category: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    body_md: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str] = mapped_column(String(256))
    source_sha256: Mapped[str] = mapped_column(String(64))
    loaded_at: Mapped[datetime] = mapped_column(UTCDateTime)


class FaultRun(Base):
    __tablename__ = "fault_runs"
    __table_args__ = (
        CheckConstraint(_in("scenario", SCENARIOS), name="scenario"),
        CheckConstraint(_in("status", FAULT_RUN_STATUSES), name="status"),
        Index("ux_fault_runs_active_host", "target_host", unique=True,
              sqlite_where=text(f"status IN {FAULT_RUN_ACTIVE}"), postgresql_where=text(f"status IN {FAULT_RUN_ACTIVE}")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario: Mapped[str] = mapped_column(String(32))
    target_host: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hold_s: Mapped[int] = mapped_column(Integer)
    stop_on_alert: Mapped[bool] = mapped_column(Boolean, default=True)
    linger_s: Mapped[int] = mapped_column(Integer, default=30)
    root_alert: Mapped[str] = mapped_column(String(128))
    expected_alerts: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    valid: Mapped[bool] = mapped_column(Boolean, default=True)
    invalid_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime)
    injected_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    injected_at_vm: Mapped[datetime | None] = mapped_column(UTCDateTime)
    vm_clock_offset_s: Mapped[float | None] = mapped_column(Float)
    eval_lag_s: Mapped[float | None] = mapped_column(Float)
    recovered_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    stop_reason: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    first_detection_s: Mapped[float | None] = mapped_column(Float)
    root_detection_s: Mapped[float | None] = mapped_column(Float)
    root_resolved_s: Mapped[float | None] = mapped_column(Float)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    alerts: Mapped[list[FaultRunAlert]] = relationship(back_populates="fault_run", cascade="all, delete-orphan")


class FaultRunAlert(Base):
    __tablename__ = "fault_run_alerts"
    __table_args__ = (
        UniqueConstraint("fault_run_id", "alert_episode_id"),
        CheckConstraint(_in("role", MATCH_ROLES), name="role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fault_run_id: Mapped[int] = mapped_column(ForeignKey("fault_runs.id", ondelete="CASCADE"))
    alert_episode_id: Mapped[int] = mapped_column(ForeignKey("alert_episodes.id"))
    role: Mapped[str] = mapped_column(String(16))
    delay_s: Mapped[float] = mapped_column(Float)

    fault_run: Mapped[FaultRun] = relationship(back_populates="alerts")
    episode: Mapped[AlertEpisode] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32))
    object_type: Mapped[str | None] = mapped_column(String(32))
    object_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    client_ip: Mapped[str | None] = mapped_column(String(64))
